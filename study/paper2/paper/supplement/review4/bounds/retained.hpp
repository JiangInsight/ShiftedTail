#pragma once
#include <bit>
#include <map>
#include <cstdlib>
#define BOOST_MATH_STANDALONE
#include <boost/math/special_functions/beta.hpp>



enum class BoundMode { shift, retained, combined, shadow };
static BoundMode bound_mode() {
  const char *s=std::getenv("REV_BOUND");
  if (!s || std::string(s)=="shift") return BoundMode::shift;
  if (std::string(s)=="retained") return BoundMode::retained;
  if (std::string(s)=="combined") return BoundMode::combined;
  if (std::string(s)=="shadow") return BoundMode::shadow;
  throw std::runtime_error("unknown REV_BOUND");
}
static const BoundMode mode=bound_mode();
static const bool legacy_beta=std::getenv("REV_LEGACY_BETA")!=nullptr;
static u64 notices=0, ranked_probes=0, binomial_queries=0, binomial_misses=0;
static u64 shift_wins[18]{}, retained_wins[18]{}, ties[18]{}, shift_only[18]{}, retained_only[18]{}, both_defer[18]{};


static inline double step(double x,bool upper) {
  if (!std::isfinite(x)) throw std::runtime_error("nonfinite endpoint");
  if (!upper && x==0.) return 0.;
  auto bits=std::bit_cast<uint64_t>(x);
  return std::bit_cast<double>(upper ? bits+1 : bits-1);
}


struct Scaled {
  double m; long long e;
  static Scaled norm(double m,long long e) {
    int delta=0; double f=std::frexp(m,&delta);
    return {f,e+delta};
  }
  static Scaled from(double x) {return norm(x,0);}
  Scaled mul(Scaled b,bool upper) const {
    return norm(step(m*b.m,upper),e+b.e);
  }
  Scaled div(Scaled b,bool upper) const {
    return norm(step(m/b.m,upper),e-b.e);
  }
  double endpoint(bool upper) const {
    if (e < -1074) return upper ? std::numeric_limits<double>::denorm_min() : 0.;
    if (e>1) return 1.;
    return std::min(1.,step(std::ldexp(m,int(e)),upper));
  }
};
static Scaled ipow(Scaled x,int d,bool upper) {
  Scaled y=Scaled::from(1.);
  for (;d;d>>=1) {
    if (d&1) y=y.mul(x,upper);
    if (d>1) x=x.mul(x,upper);
  }
  return y;
}



static double binomial_lower(int d,int k,double p) {
  if (d<k || p==0.) return 0.;
  if (p==1.) return 1.;
  bool left=k<=d-k+1;
  const double q=1.-p;
  Scaled seed=Scaled::from(left ? std::min(1.,step(q,true)) : p);
  Scaled mass=ipow(seed,d,left);
  auto odds=left ? Scaled::from(p).div(Scaled::from(step(q,false)),true)
                 : Scaled::from(step(q,false)).div(Scaled::from(p),false);
  int length=left ? k : d-k+1;
  double sum=0.;
  for(int j=0;j<length;++j) {
    sum=std::min(1.,step(sum+mass.endpoint(left),left));
    if (j+1<length) {
      auto ratio=Scaled::from(step(double(d-j)/(j+1),left));
      mass=mass.mul(odds,left).mul(ratio,left);
    }
  }
  return left ? step(1.-sum,false) : sum;
}
struct RetainedBound {
  int k;
  std::map<std::pair<int,double>,double> cache;
  template<class Alive>
  double get(const std::vector<u64>& ranked,const std::vector<double>& p,
             int d,Alive alive) {
    ++notices;
    int taken=0;
    double prod=1.,pmin=1.;
    for (auto a:ranked) {
      ++ranked_probes;
      if (!alive(a)) continue;
      prod=legacy_beta ? prod*p[a] : step(prod*p[a],false);
      if (++taken==k) break;
    }
    if (taken!=k) throw std::runtime_error("inconsistent live degree");
    for (auto it=ranked.rbegin();it!=ranked.rend();++it) {
      ++ranked_probes;
      if (alive(*it)) {pmin=p[*it]; break;}
    }
    ++binomial_queries;
    auto key=std::make_pair(d,pmin);
    auto it=cache.find(key);
    auto lower=[&](double b){return legacy_beta ? std::max(0.,std::max(prod,b)-1e-13) : std::max(prod,b);};
    if(it!=cache.end()) return lower(it->second);
    ++binomial_misses;
    double beta=legacy_beta ? (pmin==0. ? 0. : pmin==1. ? 1. :
                 boost::math::ibeta(double(k),double(d-k+1),pmin)) : binomial_lower(d,k,pmin);
    if(cache.size()<250000) cache.emplace(key,beta);
    return lower(beta);
  }
};
