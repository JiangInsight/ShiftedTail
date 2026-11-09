#pragma once
#include <algorithm>
#include <cfenv>
#include <cstdint>
#include <cfloat>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <vector>

#if defined(__FAST_MATH__) || defined(_M_FP_FAST)
#error "The certificate arithmetic requires strict floating-point evaluation."
#endif
static_assert(FLT_RADIX==2 && DBL_MANT_DIG==53 && DBL_MAX_EXP==1024 && FLT_EVAL_METHOD==0);
static_assert(std::numeric_limits<double>::is_iec559);
namespace checked_pb {
struct Interval { double lo,hi; };
struct Workspace { std::vector<double> lo,hi; };
struct Effort { size_t factors=0; uint64_t cells=0; };
inline bool supported_environment(){
    volatile double smallest=std::numeric_limits<double>::denorm_min();
    volatile double normal=std::numeric_limits<double>::min();
    volatile double half=0.5;
    volatile double tiny=normal*half;
    volatile double doubled=smallest+smallest;
    volatile double one=1., tie=0x1p-53, three_halves=0x1.8p-52;
    volatile double rounded_even=one+tie, rounded_up=one+three_halves;
    return std::fegetround()==FE_TONEAREST && rounded_even==1. && rounded_up==0x1.0000000000002p0
        && tiny>0 && doubled>smallest && smallest>0;
}
inline double down(double x){return std::nextafter(x,-INFINITY);}
inline double up(double x){return std::nextafter(x,INFINITY);}
inline double dlo(double x){return std::max(0.,down(x));}
inline double dhi(double x){return std::min(1.,up(x));}


inline Interval portable(const std::vector<double>& p,int k,Workspace& w,Effort& effort){
    if(p.size()<static_cast<size_t>(k))return {0.,0.};
    w.lo.assign(k+1,0.);w.hi.assign(k+1,0.);
    w.lo[0]=w.hi[0]=1.;
    for(double x:p){
        const double qlo=dlo(1.-x),qhi=dhi(1.-x);
        const int top=static_cast<int>(std::min<size_t>(k,++effort.factors));
        effort.cells+=top;
        for(int t=top;t>0;--t){
            const double lp=dlo(x*w.lo[t-1]),lq=dlo(qlo*w.lo[t]);
            const double hp=dhi(x*w.hi[t-1]),hq=dhi(qhi*w.hi[t]);
            w.lo[t]=dlo(lp+lq);
            w.hi[t]=dhi(hp+hq);
        }
    }
    return {w.lo[k],w.hi[k]};
}
#ifndef UCORE_NO_FMA
inline Interval fused(const std::vector<double>& p,int k,Workspace& w,Effort& effort){
    if(p.size()<static_cast<size_t>(k))return {0.,0.};
    constexpr double tau=1e-15, eps=std::numeric_limits<double>::epsilon();
    w.lo.assign(k+1,0.); auto& a=w.lo;
    int low=1,high=0;
    for(double x:p){
        ++effort.factors;
        const int top=std::min(k,high+1);
        if(top>high)a[top]=0.;
        effort.cells+=top-low+1;
        for(int t=top;t>=low;--t){
            const double prev=(t==low)?1.:a[t-1];
            const double q=1.-x,prod=q*a[t];
            a[t]=std::clamp(std::fma(x,prev,prod),0.,1.);
        }
        high=top;
        while(high>=low && a[high]<=tau){a[high]=0.;--high;}
        while(low<=high && a[low]>=1.-tau){a[low]=1.;++low;}
        if(low>k)break;
    }
    const double e=up(static_cast<double>(effort.factors)*up(8.*eps+2.*tau));
    const double center=low>k?1.:(k>high?0.:a[k]);
    return {dlo(center-e),dhi(center+e)};
}
#endif
inline Interval evaluate(const std::vector<double>& p,int k,Workspace& w,Effort& effort){
#ifdef UCORE_NO_FMA
    return portable(p,k,w,effort);
#else
    return fused(p,k,w,effort);
#endif
}
}
