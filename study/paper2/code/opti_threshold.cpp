

#define main threshold_driver_not_used
#include "uthr_study.cpp"
#undef main
#define BOOST_MATH_STANDALONE
#include <boost/math/special_functions/beta.hpp>
#include <bit>
#include <map>
#include <numeric>

struct BetaCache {
  int k;
  std::map<std::pair<int,double>,double> cache;
  double get(int d,double p) {
    if (d<k || p==0) return 0;
    if (p==1) return 1;
    auto spec=std::make_pair(d,p);
    auto it=cache.find(spec);
    if(it!=cache.end())return it->second;
    double result=boost::math::ibeta(double(k),double(d-k+1),p);
    if(cache.size()<250000)cache.emplace(spec,result);
    return result;
  }
};

int main(int argc,char** argv) {
  if(argc<7) return 2;
  const auto model=std::atoi(argv[3]);
  if(std::atoi(argv[4])!=1) {std::fprintf(stderr,"OptiUCF is sequential across k; request 1 thread\n");return 2;}
  auto graph=load(argv[1],model,std::strtoull(argv[5],nullptr,10));
  Graph support;support.n=graph.n;support.m=graph.m;support.off=graph.off;support.adj=graph.adj;
  const auto core=core_decomposition(support);support=Graph{};
  const int kmax=*std::max_element(core.begin(),core.end());
  std::vector<u32> order(graph.n);std::iota(order.begin(),order.end(),0u);
  std::stable_sort(order.begin(),order.end(),[&](u32 a,u32 b){return core[a]>core[b];});
  u32 dmax=0;std::vector<std::vector<u64>> by_p(graph.n);
  u64 sum_core=0;
  for(u32 v=0;v<graph.n;++v){
    sum_core+=core[v]; auto& a=by_p[v]; a.resize(graph.off[v+1]-graph.off[v]);
    std::iota(a.begin(),a.end(),graph.off[v]); dmax=std::max(dmax,(u32)a.size());
    std::sort(a.begin(),a.end(),[&](u64 x,u64 y){return graph.p[x]>graph.p[y];});
  }
  std::printf("graph=%s n=%u m=%llu dmax=%u kmax=%d sum_core=%llu method=opti threads=1\n",
              argv[1],graph.n,graph.m,dmax,kmax,sum_core);std::fflush(stdout);
  FILE* output=std::fopen(argv[6],"wb");if(!output)return 2;
  std::vector<double> previous(graph.n),theta(graph.n);
  Timer timer; Work work; u64 evals=0,cells=0,shortcuts=0;
  for(int k=kmax;k>=1;--k){
    std::vector<u32> next;
    for(auto v:order){if(core[v]<(u32)k)break;next.push_back(v);}
    const u64 cnt=next.size();
    std::sort(next.begin(),next.end(),[&](u32 a,u32 b){return previous[a]<previous[b];});
    std::vector<uint8_t> deleted(graph.n),active(graph.n),dirty(graph.n);
    std::vector<int> degree(graph.n);std::vector<double> key(graph.n),upper(graph.n,1.);
    using Entry=std::pair<double,u32>;
    std::priority_queue<Entry,std::vector<Entry>,std::greater<Entry>> heap;
    BetaCache beta{k,{}};size_t next_layer=0;double T=0.;
    auto eligible=[&](u32 v){return !deleted[v] && core[v]>=(u32)k;};
    auto evaluate=[&](u32 v){
      work.ps.clear();
      for(u64 a=graph.off[v];a<graph.off[v+1];++a)
        if(eligible(graph.adj[a])) work.ps.push_back(graph.p[a]);
      degree[v]=int(work.ps.size());++evals;
      key[v]=upper[v]=kprob_trunc(work.ps.data(),degree[v],k,work,cells);
      dirty[v]=0;heap.emplace(key[v],v);
    };
    auto refresh_bounds=[&](u32 v){
      int d=--degree[v];
      if(d<k || upper[v]<=T){key[v]=0.;dirty[v]=0;++shortcuts;heap.emplace(0.,v);return;}
      const auto& a=by_p[v];
      double pmin=1.,pmax=0.,prod=1.;int found=0;
      for(auto i:a)if(eligible(graph.adj[i])){
        if(!found)pmax=graph.p[i];prod*=graph.p[i];if(++found==k)break;
      }
      for(auto it=a.rbegin();it!=a.rend();++it)if(eligible(graph.adj[*it])){pmin=graph.p[*it];break;}
      upper[v]=std::min(upper[v],std::min(1.,beta.get(d,pmax)+1e-13));
      if(upper[v]<=T){key[v]=0.;dirty[v]=0;++shortcuts;}
      else {key[v]=std::max(0.,std::max(beta.get(d,pmin),prod)-1e-13);dirty[v]=1;}
      heap.emplace(key[v],v);
    };
    u64 peeled=0;
    while(peeled<cnt){
      while(!heap.empty() && (deleted[heap.top().second] || heap.top().first!=key[heap.top().second]))heap.pop();
      if(next_layer<cnt && (heap.empty() || previous[next[next_layer]]<=heap.top().first)){
        double label=previous[next[next_layer]];
        do{u32 v=next[next_layer++];active[v]=1;evaluate(v);}
        while(next_layer<cnt && previous[next[next_layer]]==label);
        continue;
      }
      if(heap.empty())throw std::runtime_error("no peel candidate");
      auto [q,v]=heap.top();heap.pop();
      if(dirty[v]){evaluate(v);continue;}
      T=std::max(T,q);theta[v]=T;deleted[v]=1;++peeled;
      for(u64 a=graph.off[v];a<graph.off[v+1];++a){auto u=graph.adj[a];if(active[u] && !deleted[u])refresh_bounds(u);}
    }
    std::vector<double> row(cnt);
    for(u64 i=0;i<cnt;++i)previous[order[i]]=row[i]=theta[order[i]];
    u32 level=k;std::fwrite(&level,4,1,output);std::fwrite(&cnt,8,1,output);std::fwrite(row.data(),8,cnt,output);
  }
  if(std::fclose(output))return 2;
  std::printf("result method=opti time=%.3fs thresholds=%llu evals=%llu cells=%llu shortcut=%llu\n",timer.sec(),sum_core,evals,cells,shortcuts);
}
