#include "graph.hpp"
#include "peel_queue.hpp"

#include <omp.h>

#include <atomic>
#include <cmath>
#include <cstring>
#include <limits>
#include <queue>

static constexpr double kTau = 1e-30;
static constexpr double kU = 0x1p-53;
static inline float enc_lb(double s);


static bool screen_tail(double mu,int d,u32 k,const std::vector<int>& offsets,
                        double& key,double& upper,float* shifted) {
  const double root=std::sqrt(double(d));
  const double guard=2.+4.*double(d)*double(d)*kU;
  const double gap=mu-guard-k;
  if (gap>=5.*root) {
    key=1.; upper=1.+2.*kU;
    for(size_t j=0;j<offsets.size();++j) {
      const double z=gap-offsets[j];
      double lower=0.;
      if (z>=5.*root) lower=1.-2.*kU;
      else if (z>=4.*root) lower=1.-2e-14;
      else if (z>=3.*root) lower=1.-2e-8;
      else if (z>=2.*root) lower=.99966;
      else if (z>=root) lower=.8646;
      else if (z>=.5*root) lower=.3934;
      shifted[j]=enc_lb(lower);
    }
    return true;
  }
  if (k-mu-guard>=5.*root) {
    key=0.;upper=2.*kU;
    std::fill_n(shifted,offsets.size(),0.f);
    return true;
  }
  return false;
}

static inline u64 splitmix64(u64 x) {
  x += 0x9e3779b97f4a7c15ULL;
  x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
  x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
  return x ^ (x >> 31);
}
static inline double hash_prob(u32 a, u32 b, u64 seed) {
  if (a > b) std::swap(a, b);
  const u64 h = splitmix64((static_cast<u64>(a) << 32 | b) ^ splitmix64(seed));
  return (static_cast<double>(h >> 32) + 1.0) * 0x1p-32;
}
static inline float float_down(double x) {
  if (x <= 0) return 0.0f;
  float f = static_cast<float>(x);
  if (static_cast<double>(f) > x) f = std::nextafter(f, 0.0f);
  return f;
}


static inline float enc_lb(double s) {
  if (s <= 0) return 0.0f;
  if (s < 0.5) return float_down(s);
  const double c = 1.0 - std::min(s, 1.0);
  float cu = static_cast<float>(c);
  if (static_cast<double>(cu) < c) cu = std::nextafter(cu, 1.0f);
  if (cu <= 0.0f) cu = std::numeric_limits<float>::denorm_min();
  return -cu;
}
static inline double dec_lb(float x) {
  if (x >= 0.0f) return static_cast<double>(x);
  return std::nextafter(1.0 + static_cast<double>(x), 0.0);
}

struct UGraph {
  u32 n = 0;
  u64 m = 0;
  std::vector<u64> off;
  std::vector<u32> adj;
  std::vector<double> p;
};

static UGraph load(const std::string& path, int model, u64 seed) {
  UGraph G;
  if (model == 5) {
    FILE* f = std::fopen(path.c_str(), "rb");
    if (!f) throw std::runtime_error("cannot open probability graph");
    u32 n; u64 arcs;
    if (std::fread(&n, 4, 1, f) != 1 || std::fread(&arcs, 8, 1, f) != 1 || arcs % 2)
      throw std::runtime_error("bad Gatd header");
    std::vector<u32> degree(n);
    G.n = n; G.m = arcs / 2; G.off.resize(static_cast<size_t>(n) + 1);
    G.adj.resize(arcs); G.p.resize(arcs);
    if (std::fread(degree.data(), 4, n, f) != n || std::fread(G.adj.data(), 4, arcs, f) != arcs ||
        std::fread(G.p.data(), 8, arcs, f) != arcs) throw std::runtime_error("incomplete Gatd input");
    std::fclose(f);
    for (u32 v=0; v<n; ++v) G.off[v+1] = G.off[v]+degree[v];
    if (G.off.back()!=arcs) throw std::runtime_error("degree sum mismatch");
    return G;
  }
  const bool wbin = path.size() > 5 && path.substr(path.size() - 5) == ".wbin";
  if (wbin) {
    FILE* f = std::fopen(path.c_str(), "rb");
    if (!f) throw std::runtime_error("cannot open " + path);
    u64 hdr[2];
    if (std::fread(hdr, 8, 2, f) != 2) throw std::runtime_error("bad header");
    G.n = static_cast<u32>(hdr[0]);
    G.m = hdr[1];
    G.off.resize(G.n + 1);
    G.adj.resize(2 * G.m);
    std::vector<u32> w(2 * G.m);
    if (std::fread(G.off.data(), 8, G.n + 1, f) != G.n + 1) throw std::runtime_error("bad off");
    if (std::fread(G.adj.data(), 4, 2 * G.m, f) != 2 * G.m) throw std::runtime_error("bad adj");
    if (std::fread(w.data(), 4, 2 * G.m, f) != 2 * G.m) throw std::runtime_error("bad w");
    std::fclose(f);
    G.p.resize(2 * G.m);
    for (u64 e = 0; e < 2 * G.m; ++e) G.p[e] = model == 4 ? -std::expm1(-0.5 * w[e]) : 0.0;
    if (model != 4)
      for (u32 v = 0; v < G.n; ++v)
        for (u64 e = G.off[v]; e < G.off[v + 1]; ++e)
          G.p[e] = model == 3 ? -std::expm1(-0.5) : hash_prob(v, G.adj[e], seed);
  } else {
    Graph g = load_bin(path);
    G.n = g.n;
    G.m = g.m;
    G.off = std::move(g.off);
    G.adj = std::move(g.adj);
    G.p.resize(G.adj.size());
    for (u32 v = 0; v < G.n; ++v)
      for (u64 e = G.off[v]; e < G.off[v + 1]; ++e)
        G.p[e] = model == 3 ? -std::expm1(-0.5) : hash_prob(v, G.adj[e], seed);
  }
  return G;
}

struct Stats {
  u64 distinct_reevaluated = 0;
  u64 evals = 0, cells = 0, shortcut = 0, exact_pops = 0, pushes = 0, removals = 0, screened = 0;
  void add(const Stats& o) {
    evals += o.evals; cells += o.cells; shortcut += o.shortcut; exact_pops += o.exact_pops; pushes += o.pushes;
    distinct_reevaluated += o.distinct_reevaluated;
    removals += o.removals; screened += o.screened;
  }
};


struct Work {
  std::vector<double> a, b, ps;
};


struct BinomialSeeds {
  struct Row {
    int low;
    double trimmed;
    std::vector<double> mass;
  };
  double p = 0.;
  std::vector<Row> rows;

  void prepare(const std::vector<double>& probabilities, u32 max_degree) {
    if (probabilities.empty()) return;
    std::vector<double> sample;
    const size_t count = std::min<size_t>(32768, probabilities.size());
    for (size_t i=0; i<count; ++i) sample.push_back(probabilities[i*probabilities.size()/count]);
    std::sort(sample.begin(), sample.end());
    size_t largest = 0;
    for (size_t i=0; i<count;) {
      size_t end = i+1;
      while (end<count && sample[end]==sample[i]) ++end;
      if (end-i>largest) { largest=end-i; p=sample[i]; }
      i=end;
    }
    if (largest*4<count) return;
    const u32 limit=std::min<u32>(max_degree,4096);
    rows.reserve(limit+1);
    rows.push_back({0,0.,{1.}});
    for (u32 d=1; d<=limit; ++d) {
      const Row& last=rows.back();
      std::vector<double> mass(last.mass.size()+1);
      for (size_t j=0; j<last.mass.size(); ++j) {
        mass[j]+=(1.-p)*last.mass[j];
        mass[j+1]=p*last.mass[j];
      }
      size_t left=0,right=mass.size();
      double lost=last.trimmed;
      while (right-left>1 && mass[left]<kTau) lost+=mass[left++];
      while (right-left>1 && mass[right-1]<kTau) lost+=mass[--right];
      rows.push_back({last.low+int(left),lost,{mass.begin()+left,mass.begin()+right}});
    }
  }
};

static double pmf_window(const double* ps, int d, Work& W, double*& f, int& lo, int& hi, u64& cells,
                         const BinomialSeeds& seeds, int matches) {
  if (W.a.size() < static_cast<size_t>(d) + 3) { W.a.resize(d + 3); W.b.resize(d + 3); }
  f = W.a.data() + 1;
  double* g = W.b.data() + 1;
  lo = 0; hi = 0;
  f[0] = 1.0;
  double T = 0;
  int skip=0;
  if (matches>=4) {
    skip=std::min<int>(matches,static_cast<int>(seeds.rows.size())-1);
    const auto& row=seeds.rows[skip];
    lo=row.low; hi=lo+int(row.mass.size())-1;
    std::copy(row.mass.begin(),row.mass.end(),f+lo);
    T=row.trimmed;
  }
  for (int i = 0; i < d; ++i) {
    const double p = ps[i], q = 1.0 - p;
    if (skip && p==seeds.p) { --skip; continue; }
    f[lo - 1] = 0.0;
    f[hi + 1] = 0.0;
    for (int j = lo; j <= hi + 1; ++j) g[j] = q * f[j] + p * f[j - 1];
    cells += static_cast<u64>(hi - lo + 2);
    ++hi;
    std::swap(f, g);
    while (lo < hi && f[lo] < kTau) { T += f[lo]; ++lo; }
    while (hi > lo && f[hi] < kTau) { T += f[hi]; --hi; }
  }
  return T;
}


static double kprob_trunc(const double* ps, int d, int k, Work& W, u64& cells) {
  if (d < k) return 0.0;
  if (k <= 0) return 1.0;
  if (W.a.size() < static_cast<size_t>(k) + 3) { W.a.resize(k + 3); W.b.resize(k + 3); }
  std::fill(W.a.begin(), W.a.begin() + k + 2, 0.0);
  std::fill(W.b.begin(), W.b.begin() + k + 2, 0.0);
  double* f = W.a.data() + 1;
  double* g = W.b.data() + 1;
  f[0] = 1.0;
  for (int i = 0; i < d; ++i) {
    const double p = ps[i], q = 1.0 - p;
    const int top = std::min(i + 1, k);
    for (int j = 0; j < top; ++j) g[j] = q * f[j] + p * f[j - 1];
    if (top == k) g[k] = f[k] + p * f[k - 1];
    else g[top] = p * f[top - 1];
    cells += static_cast<u64>(top + 1);
    std::swap(f, g);
  }
  return f[k];
}

struct Ctx {
  UGraph G;
  std::vector<u32> core, pos;
  std::vector<u32> order;
  std::vector<u64> nk;
  u32 kmax = 0;
  bool homogeneous = false;
  BinomialSeeds seeds;
  std::vector<std::vector<double>> core_tail;
  std::vector<int> O, J;
  int L = 0;

  u64 prefix_end(u32 u, u32 k) const {
    u64 e = G.off[u];
    const u64 end = G.off[u + 1];

    u64 lo = e, hi = end;
    while (lo < hi) {
      const u64 mid = (lo + hi) / 2;
      if (core[G.adj[mid]] >= k) lo = mid + 1;
      else hi = mid;
    }
    return lo;
  }
};


struct Snap {
  u32 k = 0;
  u64 n = 0;
  std::vector<double> key, ub;
  std::vector<float> lbt;
  std::vector<u32> removal_order;
};


static void peel_ctd(const Ctx& C, Snap& S, std::vector<double>& theta, Stats& st) {
  const u32 k = S.k;
  const u64 n = S.n;
  std::vector<double>& key = S.key;
  std::vector<uint8_t> removed(n, 0);
  theta.assign(n, 0.0);
  using E = std::pair<double, u32>;
  std::priority_queue<E, std::vector<E>, std::greater<E>> H;
  for (u64 i = 0; i < n; ++i) H.push({key[i], static_cast<u32>(i)});
  Work W;
  double T = 0;
  while (!H.empty()) {
    const auto [kv, i] = H.top();
    H.pop();
    if (removed[i] || kv != key[i]) continue;
    T = std::max(T, kv);
    if (std::getenv("UTHR_TRACE") && st.removals < 2000) std::printf("ctd pop i=%u key=%.6e T=%.6e\n", i, kv, T);
    theta[i] = T;
    removed[i] = 1;
    ++st.removals;
    const u32 u = C.order[i];
    const u64 pe = C.prefix_end(u, k);
    for (u64 a = C.G.off[u]; a < pe; ++a) {
      const u32 x = C.G.adj[a];
      const u32 xi = C.pos[x];
      if (removed[xi]) continue;

      W.ps.clear();
      const u64 xe = C.prefix_end(x, k);
      for (u64 b = C.G.off[x]; b < xe; ++b)
        if (!removed[C.pos[C.G.adj[b]]]) W.ps.push_back(C.G.p[b]);
      ++st.evals;
      const double nv = kprob_trunc(W.ps.data(), static_cast<int>(W.ps.size()), static_cast<int>(k), W, st.cells);
      if (nv != key[xi]) {
        key[xi] = nv;
        H.push({nv, xi});
        ++st.pushes;
      }
    }
  }
}


static void peel_lazy(const Ctx& C, Snap& S, std::vector<double>& theta, Stats& st, bool frontier) {
  const u32 k = S.k;
  const u64 n = S.n;
  const int L = C.L;
  const bool core_floor = frontier && !std::getenv("UTHR_NOCOREFLOOR");
  std::vector<uint8_t> reevaluated(n, 0);
  std::vector<double> permanent_lb(core_floor ? n : 0);
  if (core_floor) for (u32 i=0; i<n; ++i) {
    const u32 c=C.core[C.order[i]];
    permanent_lb[i]=std::max(0.0,C.core_tail[c][k]-(4.0*c+8)*kU);
  }


  std::vector<uint8_t> queued(frontier ? n : 0, 0);
  std::vector<u32> ready;
  std::vector<u32> refine;
  const bool coalesce = frontier && std::getenv("UTHR_COALESCE");
  const bool screen = frontier && std::getenv("UTHR_TAIL_SCREEN");
  const bool keep_order = std::getenv("UTHR_CERT_ORDER") != nullptr;
  if (keep_order) S.removal_order.reserve(n);
  std::vector<u64> end(frontier ? n : 0);
  std::vector<u32> degree(frontier ? n : 0);
  if (frontier) for (u32 i=0; i<n; ++i) {
    const u32 u=C.order[i]; end[i]=C.prefix_end(u,k);
    degree[i]=static_cast<u32>(end[i]-C.G.off[u]);
  }
  std::vector<double>& key = S.key;
  std::vector<double>& ub = S.ub;
  std::vector<float>& lbt = S.lbt;
  std::vector<int> r(n, 0);
  std::vector<uint8_t> removed(n, 0);
  theta.assign(n, 0.0);
  PeelQueue heap(n,frontier && std::getenv("UTHR_INDEXED"));


  static const bool no_lb = std::getenv("UTHR_NOLB") != nullptr;
  static const bool no_short = std::getenv("UTHR_NOSHORT") != nullptr;
  static const bool zero_err = std::getenv("UTHR_ZEROERR") != nullptr;
  static const bool check_eval = std::getenv("UTHR_CHECKEVAL") != nullptr;
  auto dynamic_lb = [&](u64 i) -> double {
    const int ri = r[i];
    if (ri == 0) return zero_err ? key[i] : std::max(0.0, key[i] - (ub[i] - key[i]));
    if (no_lb || ri >= static_cast<int>(C.J.size())) return 0.0;
    return dec_lb(lbt[i * L + C.J[ri]]);
  };
  auto curlb = [&](u64 i) { return std::max(core_floor ? permanent_lb[i] : 0., dynamic_lb(i)); };


  static const double tol = std::getenv("UTHR_TOL") ? std::atof(std::getenv("UTHR_TOL")) : 1e-12;
  for (u64 i = 0; i < n; ++i) {
    if (core_floor && permanent_lb[i]>=1-tol) {


      queued[i]=2; theta[i]=1.;
    } else heap.add_initial({curlb(i), static_cast<u32>(i)});
  }
  heap.build();
  Work W;
  double T = 0;
  std::vector<double> Sx;
  while (!heap.empty() || !ready.empty() || !refine.empty()) {
    u32 i;
    if (!ready.empty()) { i=ready.back(); ready.pop_back(); }
    else if (!refine.empty()) {
      i=refine.back(); refine.pop_back();
      if (removed[i] || queued[i]!=3) continue;
      queued[i]=0;
    }
    else {
      const auto top=heap.pop(); i=top.second;
      if (removed[i] || (frontier && queued[i]) || top.first!=curlb(i)) continue;
    }
    const u32 u = C.order[i];
    if (!no_short && ((frontier && degree[i]<k) || std::min(ub[i], 1.0) <= T + tol)) {
      ++st.shortcut;
    } else if (r[i] == 0) {
      ++st.exact_pops;
      T = std::max(T, key[i]);
      if (std::getenv("UTHR_TRACE") && st.removals < 2000) std::printf("lazy pop i=%u key=%.6e T=%.6e\n", i, key[i], T);
    } else {
      if (!reevaluated[i]) { reevaluated[i] = 1; ++st.distinct_reevaluated; }

      ++st.evals;
      W.ps.clear();
      const u64 pe = frontier ? end[i] : C.prefix_end(u, k);
      int matches=0;
      double mu=0.;
      for (u64 a = C.G.off[u]; a < pe; ++a) {
        if (removed[C.pos[C.G.adj[a]]]) continue;
        W.ps.push_back(C.G.p[a]);
        if (screen) mu+=C.G.p[a];
        if (!C.seeds.rows.empty() && C.G.p[a]==C.seeds.p) ++matches;
      }
      const int d = static_cast<int>(W.ps.size());
      if (d < static_cast<int>(k)) {
        key[i] = 0.0;
        ub[i] = 0.0;
        for (int j = 0; j < L; ++j) lbt[i * L + j] = 0.0f;
      } else if (screen && d>=48 && screen_tail(mu,d,k,C.O,key[i],ub[i],lbt.data()+i*L)) {
        ++st.screened;
      } else {
        double* f;
        int lo, hi;
        const double Tm = pmf_window(W.ps.data(), d, W, f, lo, hi, st.cells,C.seeds,matches);
        const double err = (2.0 * d + (hi - lo + 1) + 4) * kU * 1.01 + Tm * 1.01;

        Sx.assign(hi - lo + 2, 0.0);
        double s = 0;
        for (int t = hi; t >= lo; --t) { s += f[t]; Sx[t - lo] = s; }
        auto Sat = [&](long long t) -> double {
          if (t < lo) return s;
          if (t > hi) return 0.0;
          return Sx[t - lo];
        };
        key[i] = Sat(k);
        ub[i] = key[i] + err;
        if (check_eval) {
          u64 c2 = 0;
          Work W2;
          const double kt = kprob_trunc(W.ps.data(), d, static_cast<int>(k), W2, c2);
          if (std::fabs(kt - key[i]) > 1e-12 + 1e-9 * kt)
            std::printf("EVAL MISMATCH k=%u i=%u d=%d window=[%d,%d] key_window=%.6e key_trunc=%.6e err=%.3e\n", k, i,
                        d, lo, hi, key[i], kt, err);
        }
        for (int j = 0; j < L; ++j) lbt[i * L + j] = enc_lb(Sat(static_cast<long long>(k) + C.O[j]) - err);
      }
      r[i] = 0;
      heap.set({curlb(i), i});
      ++st.pushes;
      continue;
    }
    theta[i] = T;
    removed[i] = 1;
    if (keep_order) S.removal_order.push_back(i);
    ++st.removals;
    if (frontier && !no_short && T + tol >= 1) {
      for (u32 j=0; j<n; ++j) if (!removed[j]) {
        removed[j]=1; theta[j]=T; ++st.shortcut; ++st.removals;
        if (keep_order) S.removal_order.push_back(j);
      }
      break;
    }
    const u64 pe = frontier ? end[i] : C.prefix_end(u, k);
    for (u64 a = C.G.off[u]; a < pe; ++a) {
      const u32 xi = C.pos[C.G.adj[a]];
      if (removed[xi]) continue;
      if (frontier) {
        --degree[xi];
        if (queued[xi]==1 || queued[xi]==2) continue;
        if (!no_short && (degree[xi]<k || std::min(ub[xi],1.0)<=T+tol)) {
          queued[xi]=1; ready.push_back(xi); continue;
        }
        if (queued[xi]==3) { ++r[xi]; continue; }
      }
      const double before = curlb(xi);
      ++r[xi];
      const double after = curlb(xi);
      if (coalesce && after<=T) { queued[xi]=3; refine.push_back(xi); continue; }
      if (after != before) {
        heap.set({after, xi});
        ++st.pushes;
      }
    }
  }
  if (core_floor) for(u32 i=0;i<n;++i) if(!removed[i] && queued[i]==2){
    removed[i]=1;++st.shortcut;++st.removals;
    if(keep_order) S.removal_order.push_back(i);
  }
  for (u64 i = 0; i < n; ++i)
    if (!removed[i] && !(core_floor && permanent_lb[i]>=1-tol)) {
      std::printf("ERROR level k=%u: vertex rank %llu never removed\n", k, static_cast<unsigned long long>(i));
      break;
    }
}

int main(int argc, char** argv) {
  if (argc < 4) {
    std::fprintf(stderr, "usage: %s <graph.bin|graph.wbin> <ctd|lazy> <pmodel> [threads] [seed] [out.thr]\n", argv[0]);
    return 1;
  }
  const std::string path = argv[1], method = argv[2];
  const int model = std::atoi(argv[3]);
  const int threads = argc > 4 ? std::atoi(argv[4]) : 1;
  const u64 seed = argc > 5 ? std::strtoull(argv[5], nullptr, 10) : 1;
  const char* out = argc > 6 ? argv[6] : nullptr;
  omp_set_num_threads(threads);
  Timer tall;
  Ctx C;
  C.G = load(path, model, seed);
  const double t_load = tall.sec();
  const u32 n = C.G.n;

  {
    Graph g;
    g.n = n; g.m = C.G.m; g.off = C.G.off; g.adj = C.G.adj;
    C.core = core_decomposition(g);
  }
  for (u32 v = 0; v < n; ++v) C.kmax = std::max(C.kmax, C.core[v]);
  u32 dmax = 0;
  for (u32 v = 0; v < n; ++v) dmax = std::max<u32>(dmax, static_cast<u32>(C.G.off[v + 1] - C.G.off[v]));

  C.order.resize(n);
  for (u32 v = 0; v < n; ++v) C.order[v] = v;
  std::stable_sort(C.order.begin(), C.order.end(), [&](u32 a, u32 b) { return C.core[a] > C.core[b]; });
  C.pos.resize(n);
  for (u32 i = 0; i < n; ++i) C.pos[C.order[i]] = i;
  C.nk.assign(C.kmax + 2, 0);
  for (u32 v = 0; v < n; ++v) C.nk[C.core[v]]++;
  for (int k = static_cast<int>(C.kmax) - 1; k >= 0; --k) C.nk[k] += C.nk[k + 1];

#pragma omp parallel for schedule(dynamic, 1024)
  for (long long v = 0; v < static_cast<long long>(n); ++v) {
    const u64 b = C.G.off[v], e = C.G.off[v + 1];
    std::vector<std::pair<u32, double>> tmp;
    tmp.reserve(e - b);
    for (u64 a = b; a < e; ++a) tmp.push_back({C.G.adj[a], C.G.p[a]});
    std::stable_sort(tmp.begin(), tmp.end(), [&](const auto& x, const auto& y) { return C.core[x.first] > C.core[y.first]; });
    for (u64 a = b; a < e; ++a) { C.G.adj[a] = tmp[a - b].first; C.G.p[a] = tmp[a - b].second; }
  }

  C.O = {0, 1, 2, 3};
  for (int e = 2; (1 << e) <= static_cast<int>(dmax) + 1; ++e) {
    C.O.push_back(1 << e);
    C.O.push_back(3 << (e - 1));
  }
  C.O.push_back(static_cast<int>(dmax) + 1);
  std::sort(C.O.begin(), C.O.end());
  C.O.erase(std::unique(C.O.begin(), C.O.end()), C.O.end());
  C.L = static_cast<int>(C.O.size());
  C.J.assign(dmax + 2, 0);
  for (u32 r = 0, j = 0; r <= dmax + 1; ++r) {
    while (C.O[j] < static_cast<int>(r)) ++j;
    C.J[r] = static_cast<int>(j);
  }
  const double t_prep = tall.sec() - t_load;
  u64 sumcore = 0;
  for (u32 v = 0; v < n; ++v) sumcore += C.core[v];
  std::printf("graph=%s n=%u m=%llu dmax=%u kmax=%u sum_core=%llu method=%s pmodel=%d threads=%d L=%d load=%.2fs prep=%.2fs\n",
              path.c_str(), n, static_cast<unsigned long long>(C.G.m), dmax, C.kmax,
              static_cast<unsigned long long>(sumcore), method.c_str(), model, threads, C.L, t_load, t_prep);
  std::fflush(stdout);

  const u32 kmin_run = std::getenv("UTHR_KMIN") ? static_cast<u32>(std::atoi(std::getenv("UTHR_KMIN"))) : 1;
  const u32 kmax_run = std::getenv("UTHR_KMAX") ? static_cast<u32>(std::atoi(std::getenv("UTHR_KMAX"))) : C.kmax;


  std::vector<u64> base(n + 1);
  {
    u64 acc = 0;
    for (u32 v = 0; v < n; ++v) { base[v] = acc; acc += (C.G.off[v + 1] - C.G.off[v]) + 2; }
    base[n] = acc;
  }
  std::vector<double> pool(base[n], 0.0);
  std::vector<int> lo(n, 0), hi(n, 0);
  std::vector<double> err(n, 0.0);
  std::vector<u64> ptr(n);
  for (u32 v = 0; v < n; ++v) ptr[v] = C.G.off[v];
  std::vector<uint8_t> active(n, 0);

  Timer trun;
  if (method=="frontier") {
    auto extrema=std::minmax_element(C.G.p.begin(),C.G.p.end());
    const double floor_p=C.G.p.empty() ? 0.0 : *extrema.first;
    C.homogeneous=!C.G.p.empty() && *extrema.first==*extrema.second && !std::getenv("UTHR_NOHOMOGENEOUS");
    if (!C.homogeneous && std::getenv("UTHR_GROUP_BASE")) {
      C.seeds.prepare(C.G.p,dmax);
      std::printf("binomial seed rows=%zu p=%.17g\n",C.seeds.rows.size(),C.seeds.p);
    }
    C.core_tail.resize(C.kmax+1);
    C.core_tail[0]={1.};
    for (u32 d=1; d<=C.kmax; ++d) {
      C.core_tail[d].resize(d+1); C.core_tail[d][0]=1.;
      for (u32 t=1; t<=d; ++t)
        C.core_tail[d][t]=floor_p*C.core_tail[d-1][t-1]+(t<d?(1-floor_p)*C.core_tail[d-1][t]:0.);
    }
  }
  const bool reset_level = std::getenv("UTHR_RESET_LEVEL") != nullptr;
  u64 sweep_cells = 0, sweep_factors = 0;
  double t_sweep = 0, t_peel = 0;
  Stats total;
  double theta_sum = 0;
  u64 theta_cnt = 0;
  std::vector<u64> level_hash;
  FILE* fo = out ? std::fopen(out, "wb") : nullptr;
  const char* order_path=std::getenv("UTHR_CERT_ORDER");
  FILE* audit=order_path ? std::fopen(order_path,"wb") : nullptr;
  if ((out && !fo) || (order_path && (!audit || C.homogeneous || method=="ctd")))
      throw std::runtime_error("output or removal-order configuration invalid");
  const u32 chunk = static_cast<u32>(std::max(1, threads));
  std::vector<Snap> snaps;
  for (int k = static_cast<int>(C.kmax); k >= 1;) {
    if (C.homogeneous) {
      const u32 kk=static_cast<u32>(k--);
      if (kk<kmin_run || kk>kmax_run) continue;
      const u64 cnt=C.nk[kk]; std::vector<double> row(cnt);
      u64 h=1469598103934665603ULL;
      for (u64 i=0;i<cnt;++i) {
        const double value=C.core_tail[C.core[C.order[i]]][kk];
        row[i]=value; theta_sum+=value;
        h=(h^static_cast<u64>(std::llround(value*1e8)))*1099511628211ULL;
      }
      theta_cnt+=cnt;level_hash.push_back(h);
      if(fo){std::fwrite(&kk,4,1,fo);std::fwrite(&cnt,8,1,fo);std::fwrite(row.data(),8,cnt,fo);}
      continue;
    }

    Timer ts;
    snaps.clear();
    for (u32 c = 0; c < chunk && k >= 1; ++c, --k) {
      const u32 kk = static_cast<u32>(k);
      const u64 nk = C.nk[kk];
#pragma omp parallel for schedule(dynamic, 256) reduction(+:sweep_cells,sweep_factors)
      for (long long i = 0; i < static_cast<long long>(nk); ++i) {
        const u32 u = C.order[i];
        double* S = pool.data() + base[u];
        if (reset_level) { ptr[u] = C.G.off[u]; err[u] = 0.; }
        if (reset_level || !active[u]) {
          active[u] = 1;
          lo[u] = 0; hi[u] = 0; S[0] = 1.0;
        }
        u64 a = ptr[u];
        const u64 e = C.G.off[u + 1];
        int l = lo[u], h = hi[u];
        double er = err[u];
        for (; a < e && C.core[C.G.adj[a]] >= kk; ++a) {
          const double p = C.G.p[a], q = 1.0 - p;

          sweep_cells += static_cast<u64>(h - l + 2);
          ++sweep_factors;
          S[h + 1] = p * S[h];
          for (int t = h; t > l; --t) S[t] = q * S[t] + p * S[t - 1];
          S[l] = q * S[l] + p * 1.0;
          ++h;
          er += 3 * kU;
          while (h > l && S[h] < kTau) { er += S[h]; --h; }
          while (l < h && S[l] > 1.0 - kTau) { er += 1.0 - S[l]; ++l; }
        }
        ptr[u] = a;
        lo[u] = l; hi[u] = h; err[u] = er;
      }
      if (kk < kmin_run || kk > kmax_run) continue;
      Snap sn;
      sn.k = kk;
      sn.n = nk;
      sn.key.resize(nk);
      sn.ub.resize(nk);
      if (method != "ctd") sn.lbt.resize(nk * C.L);
#pragma omp parallel for schedule(static)
      for (long long i = 0; i < static_cast<long long>(nk); ++i) {
        const u32 u = C.order[i];
        const double* S = pool.data() + base[u];
        auto Sat = [&](long long t) -> double {
          if (t < lo[u]) return 1.0;
          if (t > hi[u]) return 0.0;
          return S[t];
        };
        const double kv = Sat(kk);
        sn.key[i] = kv;
        sn.ub[i] = kv + err[u];
        if (method != "ctd")
          for (int j = 0; j < C.L; ++j) sn.lbt[i * C.L + j] = enc_lb(Sat(static_cast<long long>(kk) + C.O[j]) - err[u]);
      }
      snaps.push_back(std::move(sn));
    }
    t_sweep += ts.sec();

    Timer tp;
    std::vector<std::vector<double>> th(snaps.size());
    std::vector<Stats> st(snaps.size());
#pragma omp parallel for schedule(dynamic, 1)
    for (long long s = 0; s < static_cast<long long>(snaps.size()); ++s) {
      if (method == "ctd") peel_ctd(C, snaps[s], th[s], st[s]);
      else peel_lazy(C, snaps[s], th[s], st[s], method=="frontier");
    }
    t_peel += tp.sec();
    for (size_t s = 0; s < snaps.size(); ++s) {
      total.add(st[s]);
      u64 h = 1469598103934665603ULL;
      for (double x : th[s]) {
        theta_sum += x;
        h = (h ^ static_cast<u64>(std::llround(x * 1e8))) * 1099511628211ULL;
      }
      theta_cnt += th[s].size();
      level_hash.push_back(h);
      if (fo) {
        const u32 kk = snaps[s].k;
        const u64 cnt = th[s].size();
        std::fwrite(&kk, 4, 1, fo);
        std::fwrite(&cnt, 8, 1, fo);
        std::fwrite(th[s].data(), 8, cnt, fo);
        if(audit){
          if(snaps[s].removal_order.size()!=cnt)throw std::runtime_error("incomplete removal order");
          std::fwrite(&kk,4,1,audit);std::fwrite(&cnt,8,1,audit);
          if(std::fwrite(snaps[s].removal_order.data(),4,cnt,audit)!=cnt)throw std::runtime_error("order write");
        }
      }
    }
    std::printf("  levels down to k=%d done: %.1fs (sweep %.1fs, peel %.1fs)\n", k + 1, trun.sec(), t_sweep, t_peel);
    std::fflush(stdout);
  }
  if (fo) std::fclose(fo);
  if (audit && std::fclose(audit)) return 2;
  if (std::getenv("UTHR_TAIL_SCREEN")) std::printf("hoeffding_resolved=%llu\n",total.screened);
  std::printf("work sweep_cells=%llu sweep_factors=%llu peel_cells=%llu repeat_calls=%llu repeated_vertex_levels=%llu\n",
              sweep_cells, sweep_factors, total.cells, total.evals, total.distinct_reevaluated);
  u64 hall = 1469598103934665603ULL;
  for (u64 h : level_hash) hall = (hall ^ h) * 1099511628211ULL;
  std::printf("result method=%s time=%.2fs sweep=%.2fs peel=%.2fs thresholds=%llu theta_sum=%.6f hash=%016llx evals=%llu "
              "cells=%.4g shortcut=%llu exact_pops=%llu pushes=%llu\n",
              method.c_str(), trun.sec(), t_sweep, t_peel, static_cast<unsigned long long>(theta_cnt), theta_sum,
              static_cast<unsigned long long>(hall), static_cast<unsigned long long>(total.evals),
              static_cast<double>(total.cells), static_cast<unsigned long long>(total.shortcut),
              static_cast<unsigned long long>(total.exact_pops), static_cast<unsigned long long>(total.pushes));
  return 0;
}
