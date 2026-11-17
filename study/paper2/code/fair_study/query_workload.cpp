#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#ifdef DIRECT
#include "uncertain-core.h"
#else
#include <omp.h>
#endif

#ifdef REFINE_QUERY
#include "boundary_query.hpp"
#endif

using Clock=std::chrono::steady_clock;
static double since(Clock::time_point start) {
    return std::chrono::duration<double>(Clock::now()-start).count();
}
#ifndef DIRECT
template<class T> static T read_one(std::ifstream& in) {
    T v{};
    if (!in.read(reinterpret_cast<char*>(&v),sizeof(v))) throw std::runtime_error("short header");
    return v;
}
#endif
int main(int argc,char** argv) {
    #ifdef REFINE_QUERY
    if(argc!=6)return 2;
#else
    if(argc!=5)return 2;
#endif
    const double queries[]={.5,.1,.9,.3,.7,.2,.8,.4,.6};
    const int threads=std::atoi(argv[2]);
    omp_set_num_threads(threads);
    auto start=Clock::now();
    std::vector<int> answer;
#ifdef DIRECT
    Uncertain_Core g;
    g.read_bin(argv[1]);
    const int alg=std::atoi(argv[3]);
    g.get_sorted_adj(alg);
    g.set_threads(threads);
#else
    std::ifstream rf(argv[3],std::ios::binary|std::ios::ate);
    if(!rf||rf.tellg()<0||rf.tellg()%4) throw std::runtime_error("invalid rank input");
    std::vector<uint32_t> rank(static_cast<size_t>(rf.tellg())/4);
    rf.seekg(0);rf.read(reinterpret_cast<char*>(rank.data()),rank.size()*4);
    std::ifstream src(argv[1],std::ios::binary);
    uint32_t kmax=read_one<uint32_t>(src);src.seekg(0);
    std::vector<std::vector<double>> level(kmax+1);
    std::vector<uint32_t> hi(rank.size(),0);
    for(uint32_t k=kmax;k>0;--k) {
        if(read_one<uint32_t>(src)!=k)throw std::runtime_error("level order");
        auto count=read_one<uint64_t>(src);
        if(count>rank.size())throw std::runtime_error("layer size");
        level[k].resize(count);
        if(!src.read(reinterpret_cast<char*>(level[k].data()),8*count))throw std::runtime_error("short layer");
        size_t previous=(k==kmax ? 0 : level[k+1].size());
        if(previous>count)throw std::runtime_error("nonmonotone support");
        std::fill(hi.begin()+previous,hi.begin()+count,k);
    }
    if(src.peek()!=EOF)throw std::runtime_error("trailing data");
    answer.resize(rank.size());
#ifdef REFINE_QUERY

    for(uint32_t k=kmax;k>1;--k)
        for(size_t j=0;j<level[k].size();++j)level[k-1][j]=std::max(level[k-1][j],level[k][j]);
    BoundaryQuery refine(argv[5]);
    std::vector<uint32_t> certain(rank.size()),possible(rank.size());
#endif
#endif
    std::cout<<std::setprecision(10)<<"READY "<<since(start)<<std::endl;
    for(int i=0;i<9;++i) {
        auto query=Clock::now();
#ifdef DIRECT
        g.set_eta(queries[i]);
        if(alg==6)g.Optimal_topdown_core_decomposition_parallel(answer,queries[i]);
        else if(alg==4)g.ImpBottomUp_core_decomposition_parallel(answer,queries[i],0);
        else return 3;
#else
#pragma omp parallel for schedule(static)
        for(long long j=0;j<static_cast<long long>(rank.size());++j) {
#ifdef REFINE_QUERY
            auto cutoff=[&](bool lower){
                uint32_t left=0,right=hi[j]+1;
                while(left+1<right){
                    auto mid=left+(right-left)/2;
                    double edge=lower?std::nextafter(level[mid][j]-1e-9,-INFINITY):std::nextafter(level[mid][j]+1e-9,INFINITY);
                    if(edge>=queries[i])left=mid;else right=mid;
                }
                return left;
            };
            certain[j]=cutoff(true);possible[j]=cutoff(false);answer[rank[j]]=certain[j];
#else
            uint32_t lo=0,end=hi[j]+1;
            while(lo+1<end) {
                uint32_t mid=lo+(end-lo)/2;
                if(level[mid][j]>=queries[i])lo=mid;else end=mid;
            }
            answer[rank[j]]=static_cast<int>(lo);
#endif
        }
#ifdef REFINE_QUERY
        refine.resolve(rank,certain,possible,kmax,queries[i],answer);
        std::cout<<"REFINE "<<i<<" "<<refine.undecided<<" "<<refine.checks<<" "<<refine.exact_checks<<std::endl;
#endif
#endif
        std::ofstream file(std::string(argv[4])+"-"+std::to_string(i)+".bin",std::ios::binary);
        file.write(reinterpret_cast<const char*>(answer.data()),answer.size()*sizeof(int));file.close();
        if(!file)throw std::runtime_error("answer write failed");
        std::cout<<"ANSWER "<<i<<" "<<queries[i]<<" "<<since(query)<<" "<<since(start)<<std::endl;
    }
    return 0;
}
