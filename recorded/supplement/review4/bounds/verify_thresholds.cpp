

#include "graph.hpp"
#include <cmath>
#include <limits>
#include <numeric>
#include <omp.h>

template<class T> static void read_all(FILE* f,T* data,size_t n) {
  if(std::fread(data,sizeof(T),n,f)!=n)throw std::runtime_error("incomplete input");
}
struct Interval{double lo,hi;};
static Interval tail(const std::vector<double>& p,int k,std::vector<double>& a){
  if(p.size()<static_cast<size_t>(k))return {0,0};
  constexpr double tau=1e-15;
  a.assign(k+1,0.);int low=1,high=0;size_t d=0;
  for(double prob:p){
    ++d; int top=std::min(k,high+1);
    if(top>high)a[top]=0.;
    for(int t=top;t>=low;--t){
      double prev=(t==low)?1.:a[t-1];
      a[t]=std::fma(prob,prev,(1.-prob)*a[t]);
    }
    high=top;
    while(high>=low && a[high]<=tau){a[high]=0.;--high;}
    while(low<=high && a[low]>=1.-tau){a[low]=1.;++low;}
    if(low>k)break;
  }


  double e=std::nextafter(double(d)*(8.*std::numeric_limits<double>::epsilon()+2.*tau),INFINITY);
  double s=low>k?1.:(k>high?0.:a[k]);
  return {std::max(0.,std::nextafter(s-e,-INFINITY)),std::min(1.,std::nextafter(s+e,INFINITY))};
}

static int verify(const char* path,const char* values,const char* removals,int threads){
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
      std::vector<double> lower_p,upper_p,buffer;
#pragma omp for schedule(dynamic,64)
      for(long long i=0;i<(long long)n;++i){
        u32 u=rank[i];double t=v[i];lower_p.clear();upper_p.clear();
        for(u64 e=g.off[u];e<g.off[u+1];++e){
          u32 w=g.adj[e];if(c[w]<(u32)k)continue;
          if(t>1e-12 && theta[w]>=t)lower_p.push_back(prob[e]);
          if(t<1.-1e-12 && removed_at[w]>removed_at[u])upper_p.push_back(prob[e]);
        }
        double lo=t<=1e-12?0.:tail(lower_p,k,buffer).lo;
        lower_deficit=std::max(lower_deficit,std::nextafter(t-lo,INFINITY));
        upper[removed_at[u]]=t>=1.-1e-12?1.:tail(upper_p,k,buffer).hi;
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
  std::printf("certificate values=%llu max_lower_deficit=%.17g max_upper_excess=%.17g unique_rounding_6dp=%llu\n",checked,worst_lower,worst_upper,unaltered6);
  return std::max(worst_lower,worst_upper)<=1e-9?0:3;
}
int main(int argc,char** argv){
  try{if(argc!=5)return 2;return verify(argv[1],argv[2],argv[3],std::atoi(argv[4]));}
  catch(const std::exception& e){std::fprintf(stderr,"%s\n",e.what());return 1;}
}
