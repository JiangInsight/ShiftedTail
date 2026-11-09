#include "graph.hpp"
#include <cmath>
#include <limits>
#include <numeric>
#include <omp.h>

template<class T> static void read_all(FILE* f,T* data,size_t n) {
  if(std::fread(data,sizeof(T),n,f)!=n)throw std::runtime_error("incomplete input");
}
#include "verified_tail.hpp"

struct WitnessStats {
  uint64_t shortcuts=0,insufficient=0,dp_calls=0,factors=0,cells=0;
  size_t max_degree=0,max_input=0,max_factors=0;
  uint64_t max_cells=0;
  void add(size_t degree,bool skip,int k,const checked_pb::Effort& e) {
    max_degree=std::max(max_degree,degree);
    if(skip){++shortcuts;return;}
    max_input=std::max(max_input,degree);
    if(degree<static_cast<size_t>(k)){++insufficient;return;}
    ++dp_calls;factors+=e.factors;cells+=e.cells;
    max_factors=std::max(max_factors,e.factors);max_cells=std::max(max_cells,e.cells);
  }
  void merge(const WitnessStats& x){
    shortcuts+=x.shortcuts;insufficient+=x.insufficient;dp_calls+=x.dp_calls;
    factors+=x.factors;cells+=x.cells;
    max_degree=std::max(max_degree,x.max_degree);max_input=std::max(max_input,x.max_input);
    max_factors=std::max(max_factors,x.max_factors);max_cells=std::max(max_cells,x.max_cells);
  }
  void report(const char* side) const {
    std::printf("witness side=%s max_degree=%zu shortcuts=%llu insufficient=%llu dp_calls=%llu max_nonshortcut_degree=%zu max_factors=%zu max_cells=%llu total_factors=%llu total_cells=%llu\n",
        side,max_degree,(unsigned long long)shortcuts,(unsigned long long)insufficient,(unsigned long long)dp_calls,max_input,max_factors,
        (unsigned long long)max_cells,(unsigned long long)factors,(unsigned long long)cells);
  }
};

static int verify(const char* path,const char* values,const char* removals,int threads){
  if(threads<1)throw std::runtime_error("thread count must be positive");
  int supported=1;
#pragma omp parallel num_threads(threads) reduction(&:supported)
  {supported &= checked_pb::supported_environment();}
  if(!supported)throw std::runtime_error("requires binary64 round-to-nearest and gradual underflow");
  const bool audit=std::getenv("UCORE_WITNESS_STATS")!=nullptr;
  std::vector<WitnessStats> lower_stats(threads),upper_stats(threads);
  FILE* f=std::fopen(path,"rb"); if(!f)throw std::runtime_error("missing graph");
  Graph g;u64 arcs;read_all(f,&g.n,1);read_all(f,&arcs,1);g.m=arcs/2;
  std::vector<u32> degree(g.n);read_all(f,degree.data(),g.n);g.off.resize(size_t(g.n)+1);
  for(u32 v=0;v<g.n;++v)g.off[v+1]=g.off[v]+degree[v];
  if(g.off.back()!=arcs)throw std::runtime_error("invalid degree sum");
  g.adj.resize(arcs);read_all(f,g.adj.data(),arcs);std::vector<double> prob(arcs);read_all(f,prob.data(),arcs);std::fclose(f);
  for(u64 e=0;e<arcs;++e)if(g.adj[e]>=g.n || !(prob[e]>=0 && prob[e]<=1))throw std::runtime_error("invalid arc");
  std::vector<u32> peel;
  auto c=core_decomposition(g,&peel);
  std::vector<u32> pos(g.n),rank(g.n);std::iota(rank.begin(),rank.end(),0u);
  for(u32 i=0;i<g.n;++i)pos[peel[i]]=i;
  for(u32 v=0;v<g.n;++v){
    u32 feasible=0,later=0;
    for(u64 e=g.off[v];e<g.off[v+1];++e){u32 u=g.adj[e];feasible+=(c[u]>=c[v]);later+=(pos[u]>pos[v]);}
    if(feasible<c[v] || later>c[v] || (pos[v] && c[peel[pos[v]-1]]>c[v]))throw std::runtime_error("support-core audit failed");
  }
  std::stable_sort(rank.begin(),rank.end(),[&](u32 a,u32 b){return c[a]>c[b];});
  FILE* fv=std::fopen(values,"rb");FILE* fo=std::fopen(removals,"rb");
  if(!fv||!fo)throw std::runtime_error("missing threshold or order file");
  std::vector<double> theta(g.n);std::vector<u32> removed_at(g.n);
  double worst_lower=0.,worst_upper=0.;u64 checked=0,unaltered6=0;
  for(int k=c[rank.front()];k>=1;--k){
    u32 a,b;u64 n,m;read_all(fv,&a,1);read_all(fo,&b,1);read_all(fv,&n,1);read_all(fo,&m,1);
    if(a!=(u32)k||a!=b||m!=n||!n||n>g.n||c[rank[n-1]]<(u32)k||(n<g.n && c[rank[n]]>=(u32)k))throw std::runtime_error("invalid layer");
    std::vector<double> v(n),upper(n);std::vector<u32> order(n);std::vector<char> seen(n);
    read_all(fv,v.data(),n);read_all(fo,order.data(),n);
    for(u32 i=0;i<n;++i){
      if(order[i]>=n || seen[order[i]]++)throw std::runtime_error("invalid removal permutation");
      if(!(v[i]>=-1e-9 && v[i]<=1.+1e-9))throw std::runtime_error("bad threshold");
      removed_at[rank[order[i]]]=i;theta[rank[i]]=v[i];
    }
    double lower_deficit=0.;
#pragma omp parallel num_threads(threads) reduction(max:lower_deficit)
    {
      std::vector<double> lower_p,upper_p;
      checked_pb::Workspace buffer;
#pragma omp for schedule(dynamic,64)
      for(long long i=0;i<(long long)n;++i){
        u32 u=rank[i];double t=v[i];lower_p.clear();upper_p.clear();
        const bool skip_lower=t<=1e-12,skip_upper=t>=1.-1e-12;
        size_t lower_degree=0,upper_degree=0;
        for(u64 e=g.off[u];e<g.off[u+1];++e){
          u32 w=g.adj[e];if(c[w]<(u32)k)continue;
          if(theta[w]>=t){++lower_degree;if(!skip_lower)lower_p.push_back(prob[e]);}
          if(removed_at[w]>removed_at[u]){++upper_degree;if(!skip_upper)upper_p.push_back(prob[e]);}
        }
        checked_pb::Effort le,ue;
        double lo=skip_lower?0.:checked_pb::evaluate(lower_p,k,buffer,le).lo;
        lower_deficit=std::max(lower_deficit,std::nextafter(t-lo,INFINITY));
        upper[removed_at[u]]=skip_upper?1.:checked_pb::evaluate(upper_p,k,buffer,ue).hi;
        if(audit){
          const int tid=omp_get_thread_num();
          lower_stats[tid].add(lower_degree,skip_lower,k,le);
          upper_stats[tid].add(upper_degree,skip_upper,k,ue);
        }
      }
    }
    double upper_excess=0.,prefix=0.;
    for(u32 i=0;i<n;++i){
      prefix=std::max(prefix,upper[i]);
      upper_excess=std::max(upper_excess,std::nextafter(prefix-v[order[i]],INFINITY));
    }
    worst_lower=std::max(worst_lower,lower_deficit);worst_upper=std::max(worst_upper,upper_excess);
    for(double x:v){

      double ls=std::nextafter(std::nextafter(x-lower_deficit,-INFINITY)*1e6,-INFINITY);
      double hs=std::nextafter(std::nextafter(x+upper_excess,INFINITY)*1e6,INFINITY);
      unaltered6+=std::llround(ls)==std::llround(hs);
    }
    checked+=n;
    if(k%20==0||k==1){std::printf("k=%d checked=%llu lower_deficit=%.9g upper_excess=%.9g\n",k,checked,worst_lower,worst_upper);std::fflush(stdout);}
  }
  if(std::fgetc(fv)!=EOF ||std::fgetc(fo)!=EOF)throw std::runtime_error("unexpected trailing data");
  std::fclose(fv);std::fclose(fo);
  if(audit){
    WitnessStats lower,upper;
    for(int t=0;t<threads;++t){lower.merge(lower_stats[t]);upper.merge(upper_stats[t]);}
    lower.report("lower");upper.report("upper");
  }
  std::printf("certificate values=%llu max_lower_deficit=%.17g max_upper_excess=%.17g unique_rounding_6dp=%llu\n",checked,worst_lower,worst_upper,unaltered6);
  return std::max(worst_lower,worst_upper)<=1e-9?0:3;
}
int main(int argc,char** argv){
  try{if(argc!=5)return 2;return verify(argv[1],argv[2],argv[3],std::atoi(argv[4]));}
  catch(const std::exception& e){std::fprintf(stderr,"%s\n",e.what());return 1;}
}
