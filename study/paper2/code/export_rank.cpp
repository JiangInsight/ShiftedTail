
#include "graph.hpp"
#include <numeric>
int main(int argc,char** argv){
  if(argc!=3 && argc!=4)return 2;
  FILE* f=std::fopen(argv[1],"rb");if(!f)return 2;
  Graph g;u64 arcs;
  if(std::fread(&g.n,4,1,f)!=1||std::fread(&arcs,8,1,f)!=1)return 1;
  g.m=arcs/2;g.off.resize(g.n+1);
  std::vector<u32> deg(g.n);g.adj.resize(arcs);
  if(std::fread(deg.data(),4,g.n,f)!=g.n||std::fread(g.adj.data(),4,arcs,f)!=arcs)return 1;
  std::fclose(f);
  for(u32 i=0;i<g.n;++i)g.off[i+1]=g.off[i]+deg[i];
  if(g.off.back()!=arcs)return 1;
  std::vector<u32> peel;
  auto c=core_decomposition(g,&peel);std::vector<u32> order(g.n);std::iota(order.begin(),order.end(),0);
  std::stable_sort(order.begin(),order.end(),[&](u32 a,u32 b){return c[a]>c[b];});
  if(argc==4){
    std::vector<u32> pos(g.n);
    for(u32 i=0;i<g.n;++i)pos[peel[i]]=i;
    for(u32 v=0;v<g.n;++v){
      u32 inside=0,later=0;
      for(u64 a=g.off[v];a<g.off[v+1];++a){u32 w=g.adj[a];inside+=(c[w]>=c[v]);later+=(pos[w]>pos[v]);}
      if(inside<c[v] || later>c[v] || (pos[v] && c[peel[pos[v]-1]]>c[v]))return 3;
    }
    std::vector<u32> ranked(g.n);for(u32 i=0;i<g.n;++i)ranked[i]=c[order[i]];
    FILE* cf=std::fopen(argv[3],"wb");if(!cf)return 1;
    if(std::fwrite(ranked.data(),4,g.n,cf)!=g.n || std::fclose(cf))return 1;
  }
  f=std::fopen(argv[2],"wb");if(!f)return 1;
  auto written=std::fwrite(order.data(),4,g.n,f);return std::fclose(f)||written!=g.n;
}
