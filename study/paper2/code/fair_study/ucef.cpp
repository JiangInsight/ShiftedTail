#include "../graph.hpp"
#include <cmath>
#include <numeric>
#include <stdexcept>
#include <omp.h>




struct ProbGraph {
    Graph g;
    std::vector<double> p;
    std::vector<u32> core,rank,position,visit;
    std::vector<size_t> end;
    explicit ProbGraph(const char* path){
        FILE* f=std::fopen(path,"rb");if(!f)throw std::runtime_error("open graph");
        uint64_t arcs;
        if(fread(&g.n,4,1,f)!=1||fread(&arcs,8,1,f)!=1)throw std::runtime_error("bad header");
        g.m=arcs/2;std::vector<u32> deg(g.n);
        g.off.resize(size_t(g.n)+1);g.adj.resize(arcs);p.resize(arcs);
        if(fread(deg.data(),4,g.n,f)!=g.n||fread(g.adj.data(),4,arcs,f)!=arcs||fread(p.data(),8,arcs,f)!=arcs)
            throw std::runtime_error("truncated graph");
        fclose(f);for(u32 i=0;i<g.n;++i)g.off[i+1]=g.off[i]+deg[i];
        if(g.off.back()!=arcs)throw std::runtime_error("degree sum");
        core=core_decomposition(g);rank.resize(g.n);std::iota(rank.begin(),rank.end(),0);
        std::stable_sort(rank.begin(),rank.end(),[&](u32 a,u32 b){return core[a]>core[b];});
        position.resize(g.n);for(u32 i=0;i<g.n;++i)position[rank[i]]=i;
        std::vector<double> any(g.n);
        for(u32 i=0;i<g.n;++i){
            std::vector<std::pair<u32,double>> row;
            double log0=0;
            for(u64 e=g.off[i];e<g.off[i+1];++e){row.emplace_back(g.adj[e],p[e]);log0+=std::log1p(-p[e]);}
            any[i]=-std::expm1(log0);
            std::stable_sort(row.begin(),row.end(),[&](auto a,auto b){return core[a.first]>core[b.first];});
            u64 e=g.off[i];for(auto x:row){g.adj[e]=x.first;p[e++]=x.second;}
        }
        visit=rank;
        std::stable_sort(visit.begin(),visit.end(),[&](u32 a,u32 b){return core[a]!=core[b]?core[a]<core[b]:any[a]<any[b];});
    }
    std::vector<double> layer(u32 k,const std::vector<double>& prior) const {
        size_t count=std::partition_point(rank.begin(),rank.end(),[&](u32 u){return core[u]>=k;})-rank.begin();
        std::vector<double> t(prior.begin(),prior.begin()+count),dp(k+1);
        std::vector<char> active(count,1);
        std::vector<std::pair<double,double>> peers;
        auto first=std::lower_bound(visit.begin(),visit.end(),k,[&](u32 v,u32 x){return core[v]<x;});
        bool again=true;
        while(again) {
            again=false;
            for(auto it=first;it!=visit.end();++it) {
                u32 u=*it,r=position[u];if(!active[r])continue;
                active[r]=false;peers.clear();
                for(u64 e=g.off[u];e<g.off[u+1];++e){
                    u32 v=g.adj[e];if(core[v]<k)break;
                    peers.emplace_back(t[position[v]],p[e]);
                }
                std::sort(peers.begin(),peers.end(),std::greater<std::pair<double,double>>());
                std::fill(dp.begin(),dp.end(),0.);dp[0]=1.;
                double old=t[r],best=0.;size_t degree=0;
                for(auto [limit,pedge]:peers){
                    if(limit<=best || best>=old)break;
                    for(size_t j=std::min<size_t>(++degree,k);j>0;--j)
                        dp[j]=(1.-pedge)*dp[j]+pedge*dp[j-1];
                    best=std::max(best,std::min(limit,dp[k]));
                }
                t[r]=std::min(old,best);
                if(t[r]==old)continue;
                for(u64 e=g.off[u];e<g.off[u+1];++e){
                    u32 v=g.adj[e];if(core[v]<k)break;u32 vr=position[v];
                    if(t[r]<t[vr] && t[vr]<=old){active[vr]=true;again=true;}
                }
            }
        }
        return t;
    }
};

int main(int argc,char** argv){
    if(argc!=4)return 2;
    int workers=std::atoi(argv[2]);if(workers<1)return 2;
    ProbGraph h(argv[1]);u32 max=h.core[h.rank[0]];
    std::vector<std::vector<double>> rows(max+1);
    rows[0].assign(h.g.n,1.);
    for(u32 start=1;start<=max;start+=workers){
        int end=std::min<int>(max+1,start+workers);
#pragma omp parallel for schedule(dynamic,1) num_threads(workers)
        for(int k=start;k<end;++k)rows[k]=h.layer(k,rows[start-1]);
    }
    FILE* f=fopen(argv[3],"wb");if(!f)return 2;
    for(u32 k=max;k>0;--k){uint64_t n=rows[k].size();
        if(fwrite(&k,4,1,f)!=1||fwrite(&n,8,1,f)!=1||fwrite(rows[k].data(),8,n,f)!=n)return 2;
    }
    return fclose(f)==0?0:2;
}
