#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>
#include "../fair_study/boundary_query.hpp"
int main(int argc,char** argv){
    if(argc<5)return 2;
    const unsigned n=std::stoul(argv[2]),k=std::stoul(argv[3]);
    std::vector<uint32_t> rank(n),lo(n,k-1),hi(n,k);
    std::iota(rank.begin(),rank.end(),0u);
    BoundaryQuery backend(argv[1]);
    for(int j=4;j<argc;++j){
        const double eta=std::strtod(argv[j],nullptr);
        std::vector<int> answer(n,k-1);const auto start=std::chrono::steady_clock::now();
        backend.resolve(rank,lo,hi,k,eta,answer);
        const double total=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
        std::ofstream output(std::string(argv[1])+".q"+std::to_string(j-4)+".answers",std::ios::binary);
        output.exceptions(std::ios::badbit|std::ios::failbit);
        output.write(reinterpret_cast<const char*>(answer.data()),std::streamsize(answer.size()*sizeof(int)));
        auto kept=std::count(answer.begin(),answer.end(),static_cast<int>(k));
        uint64_t hash=14695981039346656037ULL;
        for(int a:answer)for(int j=0;j<4;++j){hash^=(static_cast<uint32_t>(a)>>(8*j))&255;hash*=1099511628211ULL;}
        std::printf("query id=%d eta=%.17g candidates=%llu checks=%llu revisits=%llu exact=%llu retained=%zu min_answer=%d max_answer=%d observed_denominator_bits=%zu comparison_bits=%zu exact_factors=%zu exact_s=%.9f load_s=%.9f service_s=%.9f answer_hash=%llu\n",
           j-4,eta,(unsigned long long)backend.undecided,(unsigned long long)backend.checks,(unsigned long long)(backend.checks-backend.undecided),
           (unsigned long long)backend.exact_checks,static_cast<size_t>(kept),*std::min_element(answer.begin(),answer.end()),*std::max_element(answer.begin(),answer.end()),
           backend.max_denominator_bits,backend.max_comparison_bits,backend.max_factors,backend.exact_seconds,backend.load_seconds,total,(unsigned long long)hash);
    }
}
