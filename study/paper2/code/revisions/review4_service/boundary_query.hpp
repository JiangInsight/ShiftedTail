#pragma once
#include <cmath>
#ifdef UCORE_BOUNDARY_STATS
#include <chrono>
#endif
#include <cstring>
#include <gmpxx.h>
#include <limits>
#include <queue>



class BoundaryQuery {
#ifdef UCORE_BOUNDARY_STATS
    using clock_type=std::chrono::steady_clock;
    static size_t bits(const mpz_class& x){return x==0?0:mpz_sizeinbase(x.get_mpz_t(),2);}
#endif
    std::vector<uint64_t> offsets_;
    std::vector<uint32_t> neighbor_;
    std::vector<double> probability_;
    std::vector<uint32_t> inverse_, removed_;
    std::string path_;
    static double lower(double x) { return std::max(0.,std::nextafter(x,-INFINITY)); }
    static double upper(double x) { return std::min(1.,std::nextafter(x,INFINITY)); }
    struct Dyadic { mpz_class numerator; int power; };
    static Dyadic dyadic(double v) {
        if(v==0.) return {0,0};
        int exp=0;double mant=std::frexp(v,&exp);
        mpz_class num;mpz_set_d(num.get_mpz_t(),std::ldexp(mant,53));
        auto zeros=mpz_scan1(num.get_mpz_t(),0);
        return {num>>zeros,53-exp-static_cast<int>(zeros)};
    }
    void load(const std::vector<uint32_t>& rank) {
        std::ifstream f(path_,std::ios::binary);f.exceptions(std::ios::badbit|std::ios::failbit);
        uint32_t n;uint64_t arcs;f.read(reinterpret_cast<char*>(&n),4);f.read(reinterpret_cast<char*>(&arcs),8);
        if(n!=rank.size())throw std::runtime_error("graph/index vertices differ");
        std::vector<uint32_t> deg(n);f.read(reinterpret_cast<char*>(deg.data()),n*4ULL);
        offsets_.resize(n+1);inverse_.resize(n);removed_.resize(n);
        for(size_t i=0;i<n;++i){offsets_[i+1]=offsets_[i]+deg[i];inverse_[rank[i]]=i;}
        if(offsets_.back()!=arcs)throw std::runtime_error("degree sum");
        neighbor_.resize(arcs);probability_.resize(arcs);
        f.read(reinterpret_cast<char*>(neighbor_.data()),4*arcs);f.read(reinterpret_cast<char*>(probability_.data()),8*arcs);
    }
    bool feasible(uint32_t v,uint32_t k,double eta,const std::vector<uint32_t>& hi) {
        ++checks;
        std::vector<double> probs;
        std::vector<double> lo(k+1),up(k+1);
        lo[0]=up[0]=1.;
        for(uint64_t pos=offsets_[v];pos<offsets_[v+1];++pos) {
            uint32_t nbr=neighbor_[pos];
            if(hi[inverse_[nbr]]<k || removed_[nbr]==k) continue;
            double p=probability_[pos];probs.push_back(p);
            double qlo=lower(1.-p),qhi=upper(1.-p);
            for(size_t t=std::min<size_t>(k,probs.size());t>0;--t) {
                lo[t]=lower(lower(qlo*lo[t])+lower(p*lo[t-1]));
                up[t]=upper(upper(qhi*up[t])+upper(p*up[t-1]));
            }
            if(lo[k]>=eta)return true;
        }
        if(probs.size()<k || up[k]<eta)return false;
        ++exact_checks;
#ifdef UCORE_BOUNDARY_STATS
        const auto start=clock_type::now();
        auto exact_result=[&](bool x){
            exact_seconds+=std::chrono::duration<double>(clock_type::now()-start).count();return x;
        };
#endif
        const auto target=dyadic(eta);
        std::vector<mpz_class> survival(k+1);survival[0]=1;
        size_t seen=0;
        for(double p:probs) {
            const auto x=dyadic(p);
            mpz_class denom=mpz_class(1)<<x.power;
            mpz_class q=denom-x.numerator;
            for(size_t t=std::min<size_t>(++seen,k);t>0;--t)
                survival[t]=q*survival[t]+x.numerator*survival[t-1];
            survival[0]<<=x.power;
#ifdef UCORE_BOUNDARY_STATS
            mpz_class left=survival[k]<<target.power, right=survival[0]*target.numerator;
            max_denominator_bits=std::max(max_denominator_bits,bits(survival[0]));
            max_comparison_bits=std::max({max_comparison_bits,bits(left),bits(right)});
            max_factors=std::max(max_factors,seen);
            if(left>=right)return exact_result(true);
#else
            if((survival[k]<<target.power)>=survival[0]*target.numerator)return true;
#endif
        }
#ifdef UCORE_BOUNDARY_STATS
        return exact_result(false);
#else
        return false;
#endif
    }
 public:
#ifdef UCORE_BOUNDARY_STATS
    double load_seconds=0,exact_seconds=0;
    size_t max_denominator_bits=0,max_comparison_bits=0,max_factors=0;
#endif
    uint64_t checks=0,exact_checks=0,undecided=0;
    explicit BoundaryQuery(const char* path):path_(path){}
    void resolve(const std::vector<uint32_t>& rank,const std::vector<uint32_t>& lo,const std::vector<uint32_t>& hi,
                 uint32_t kmax,double eta,std::vector<int>& answer) {
        checks=exact_checks=undecided=0;
        std::vector<std::vector<uint32_t>> buckets(kmax+1);
        for(size_t i=0;i<rank.size();++i) for(uint32_t k=lo[i]+1;k<=hi[i];++k) {
            buckets[k].push_back(rank[i]);++undecided;
        }
#ifdef UCORE_BOUNDARY_STATS
        load_seconds=exact_seconds=0;
        max_denominator_bits=max_comparison_bits=max_factors=0;
#endif
        if(!undecided)return;
        if(offsets_.empty()){
#ifdef UCORE_BOUNDARY_STATS
            const auto start=clock_type::now();
#endif
            load(rank);
#ifdef UCORE_BOUNDARY_STATS
            load_seconds=std::chrono::duration<double>(clock_type::now()-start).count();
#endif
        }
        std::fill(removed_.begin(),removed_.end(),0);
        std::vector<char> queued(rank.size());
        for(uint32_t k=1;k<=kmax;++k) {
            std::queue<uint32_t> q;
            for(auto v:buckets[k]){q.push(v);queued[v]=true;}
            while(!q.empty()){
                auto v=q.front();q.pop();queued[v]=false;
                if(feasible(v,k,eta,hi))continue;
                removed_[v]=k;
                for(auto pos=offsets_[v];pos<offsets_[v+1];++pos){
                    auto u=neighbor_[pos],r=inverse_[u];
                    if(lo[r]<k && k<=hi[r] && removed_[u]!=k && !queued[u]){q.push(u);queued[u]=true;}
                }
            }
            for(auto v:buckets[k])if(removed_[v]!=k)answer[v]=static_cast<int>(k);
        }
    }
};
