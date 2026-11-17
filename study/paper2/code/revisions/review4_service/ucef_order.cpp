

#include "../../graph.hpp"
#include <cmath>
#include <numeric>
#include <omp.h>
#include <atomic>
#include <stdexcept>
#include <vector>

template<class T> static void get(FILE* f,T* a,size_t n) {
    if(fread(a,sizeof(T),n,f)!=n)throw std::runtime_error("truncated input");
}
template<class T> static void put(FILE* f,const T* a,size_t n) {
    if(fwrite(a,sizeof(T),n,f)!=n)throw std::runtime_error("write failure");
}
struct Data {
    Graph graph;
    std::vector<double> prob;
    std::vector<u32> rank,position;
    explicit Data(const char* name) {
        FILE* f=fopen(name,"rb");if(!f)throw std::runtime_error("missing graph");
        u64 arcs;get(f,&graph.n,1);get(f,&arcs,1);
        graph.m=arcs/2;graph.off.resize(size_t(graph.n)+1);
        std::vector<u32> degrees(graph.n);get(f,degrees.data(),degrees.size());
        for(u32 j=0;j<graph.n;++j)graph.off[j+1]=graph.off[j]+degrees[j];
        if(graph.off.back()!=arcs)throw std::runtime_error("degree sum");
        graph.adj.resize(arcs);prob.resize(arcs);get(f,graph.adj.data(),arcs);get(f,prob.data(),arcs);fclose(f);
        auto core=core_decomposition(graph);
        rank.resize(graph.n);std::iota(rank.begin(),rank.end(),0u);
        std::stable_sort(rank.begin(),rank.end(),[&](u32 a,u32 b){return core[a]>core[b];});
        position.resize(graph.n);
        for(u32 j=0;j<graph.n;++j)position[rank[j]]=j;
        for(auto& u:graph.adj)u=position[u];
    }

    bool eligible(u32 r,int k,double ceiling,const std::vector<char>& state,std::vector<double>& tail)const {
        if(ceiling>=1.)return true;
        std::fill(tail.begin(),tail.end(),0.);tail[0]=1.;
        int low=1,high=0;u32 u=rank[r];
        for(u64 e=graph.off[u];e<graph.off[u+1];++e){
            u32 s=graph.adj[e];if(s>=state.size() || state[s]==3)continue;
            double p=prob[e];int top=std::min(k,high+1);
            if(top>high)tail[top]=0.;
            for(int j=top;j>=low;--j)tail[j]=p*tail[j-1]+(1.-p)*tail[j];
            high=top;
            while(high>=low&&tail[high]<1e-15){tail[high--]=0.;}
            while(low<=high&&tail[low]>1.-1e-15){tail[low++]=1.;}
            if(tail[k]>ceiling)return false;
        }
        return true;
    }
    bool order(int k,const std::vector<double>& row,std::vector<u32>& out) const {
        const size_t n=row.size();
        std::vector<u32> sorted(n),queue;std::iota(sorted.begin(),sorted.end(),0u);
        std::sort(sorted.begin(),sorted.end(),[&](u32 a,u32 b){return row[a]!=row[b]?row[a]<row[b]:a<b;});
        std::vector<char> state(n);
        std::vector<double> tail(k+1);out.reserve(n);
        for(size_t first=0;first<n;){
            size_t end=first+1;
            while(end<n && row[sorted[end]]-row[sorted[first]]<=1e-11)++end;
            if(end==first+1){state[sorted[first]]=3;out.push_back(sorted[first]);first=end;continue;}
            queue.assign(sorted.begin()+first,sorted.begin()+end);
            for(u32 r:queue)state[r]=1;
            for(size_t i=0;i<queue.size();++i){
                u32 r=queue[i];
                if(!eligible(r,k,row[r]+2e-10,state,tail)){state[r]=2;continue;}
                state[r]=3;out.push_back(r);
                u32 u=rank[r];
                for(u64 e=graph.off[u];e<graph.off[u+1];++e){
                    u32 s=graph.adj[e];
                    if(s<n&&state[s]==2){state[s]=1;queue.push_back(s);}
                }
            }
            if(out.size()!=end){fprintf(stderr,"stuck k=%d at=%zu end=%zu remaining=%zu\n",k,first,end,end-out.size());return false;}
            first=end;
        }
        return true;
    }
};
int main(int argc,char** argv){
    if(argc!=5)return 2;
    Data data(argv[1]);FILE* f=fopen(argv[2],"rb");if(!f)return 2;
    u32 top;get(f,&top,1);rewind(f);
    std::vector<std::vector<double>> rows(top+1);
    std::vector<std::vector<u32>> orders(top+1);
    for(u32 k=top;k>0;--k){
        u32 l;u64 n;get(f,&l,1);get(f,&n,1);
        if(l!=k||n>data.rank.size()||!n)return 2;
        rows[k].resize(n);get(f,rows[k].data(),n);
        for(double t:rows[k])if(!(t>=0&&t<=1.+1e-12))return 3;
    }
    if(fgetc(f)!=EOF)return 2;fclose(f);
    const int threads=atoi(argv[4]);std::atomic<bool> failed=false;
#pragma omp parallel for schedule(dynamic,1) num_threads(threads)
    for(int k=1;k<=static_cast<int>(top);++k)
        if(!failed.load()&&!data.order(k,rows[k],orders[k]))failed.store(true);
    if(failed)return 3;
    f=fopen(argv[3],"wb");if(!f)return 2;
    for(u32 k=top;k>0;--k){u64 n=orders[k].size();put(f,&k,1);put(f,&n,1);put(f,orders[k].data(),n);}
    return fclose(f)?2:0;
}
