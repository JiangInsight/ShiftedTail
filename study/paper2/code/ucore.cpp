




























#include "graph.hpp"

#include <omp.h>

#include <atomic>
#include <cmath>
#include <cstring>

static constexpr double kTau = 1e-30;
static constexpr double kU = 0x1p-53;

static inline u64 splitmix64(u64 x) {
  x += 0x9e3779b97f4a7c15ULL;
  x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
  x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
  return x ^ (x >> 31);
}

static inline double edge_prob(u32 a, u32 b, u64 seed, int model) {
  if (a > b) std::swap(a, b);
  const u64 h = splitmix64((static_cast<u64>(a) << 32 | b) ^ splitmix64(seed));
  const double x = (static_cast<double>(h >> 32) + 1.0) * 0x1p-32;
  if (model == 1) return 0.5 + 0.5 * x;
  if (model == 2) return 0.5 * x;
  return x;
}

struct Stats {
  u64 cells = 0, evals = 0, amb = 0, rounds = 0;
};

struct Work {
  std::vector<double> a, b, ps;
};


struct dd {
  double hi, lo;
};
static inline dd two_sum(double a, double b) {
  double s = a + b, bb = s - a;
  return {s, (a - (s - bb)) + (b - bb)};
}
static inline dd dd_add(dd a, dd b) {
  dd s = two_sum(a.hi, b.hi);
  s.lo += a.lo + b.lo;
  return two_sum(s.hi, s.lo);
}
static inline dd dd_mul_d(dd a, double b) {
  double p = a.hi * b;
  double e = std::fma(a.hi, b, -p);
  e += a.lo * b;
  return two_sum(p, e);
}

static void survival_dd(const double* ps, int d, std::vector<double>& S) {
  std::vector<dd> f(d + 2, dd{0, 0}), g(d + 2, dd{0, 0});
  f[0] = {1, 0};
  for (int i = 0; i < d; ++i) {
    const double p = ps[i], q = 1.0 - p;
    g[0] = dd_mul_d(f[0], q);
    for (int j = 1; j <= i + 1; ++j) g[j] = dd_add(dd_mul_d(f[j], q), dd_mul_d(f[j - 1], p));
    std::swap(f, g);
  }
  S.assign(d + 2, 0.0);
  dd s{0, 0};
  for (int t = d; t >= 0; --t) {
    s = dd_add(s, f[t]);
    S[t] = s.hi + s.lo;
  }
}



static double pmf_window(const double* ps, int d, Work& W, double*& f, int& lo, int& hi, u64& cells) {
  if (W.a.size() < static_cast<size_t>(d) + 3) { W.a.resize(d + 3); W.b.resize(d + 3); }
  f = W.a.data() + 1;
  double* g = W.b.data() + 1;
  lo = 0; hi = 0;
  f[0] = 1.0;
  double T = 0;
  for (int i = 0; i < d; ++i) {
    const double p = ps[i], q = 1.0 - p;
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


static int eta_degree(const double* ps, int d, double eta, Work& W, Stats& st) {
  if (d == 0) return 0;
  double* f;
  int lo, hi;
  const double T = pmf_window(ps, d, W, f, lo, hi, st.cells);
  const double gam = (2.0 * d + (hi - lo + 1) + 4) * kU * 1.01;
  double S = 0, Snext = 0;
  int e = lo - 1;
  for (int t = hi; t >= lo; --t) {
    Snext = S;
    S += f[t];
    if (S >= eta) { e = t; break; }
  }
  if (e == lo - 1) { Snext = S; S = 1.0 - T; }

  const bool ok_true = (e == lo - 1) ? (S * (1 - gam) - 2 * T >= eta) : (S * (1 - gam) >= eta);
  const bool ok_false = ((Snext + T) * (1 + 2 * gam) < eta);
  if (ok_true && ok_false) return e;
  ++st.amb;
  std::vector<double> Sx;
  survival_dd(ps, d, Sx);
  int ex = 0;
  for (int t = d; t >= 0; --t)
    if (Sx[t] >= eta) { ex = t; break; }
  return ex;
}


static bool check_trunc(const double* ps, int d, int e, double eta, Work& W, Stats& st) {
  if (e <= 0) return true;
  if (d < e) return false;
  if (W.a.size() < static_cast<size_t>(e) + 3) { W.a.resize(e + 3); W.b.resize(e + 3); }
  std::fill(W.a.begin(), W.a.begin() + e + 2, 0.0);
  std::fill(W.b.begin(), W.b.begin() + e + 2, 0.0);
  double* f = W.a.data() + 1;
  double* g = W.b.data() + 1;
  f[0] = 1.0;
  for (int i = 0; i < d; ++i) {
    const double p = ps[i], q = 1.0 - p;
    const int top = std::min(i + 1, e);
    for (int j = 0; j < top && j < e; ++j) g[j] = q * f[j] + p * f[j - 1];
    if (top == e) g[e] = f[e] + p * f[e - 1];
    else g[top] = p * f[top - 1];
    st.cells += static_cast<u64>(top + 1);
    std::swap(f, g);
  }
  const double S = f[e];
  const double gam = (2.0 * d + 4) * kU * 1.01;
  if (S * (1 - gam) >= eta) return true;
  if (S * (1 + 2 * gam) < eta) return false;
  ++st.amb;
  std::vector<double> Sx;
  survival_dd(ps, d, Sx);
  return Sx[e] >= eta;
}


static int eta_degree_trunc(const double* ps, int d, int cap, double eta, Work& W, Stats& st) {
  cap = std::min(cap, d);
  if (cap <= 0) return 0;
  if (W.a.size() < static_cast<size_t>(cap) + 3) { W.a.resize(cap + 3); W.b.resize(cap + 3); }
  std::fill(W.a.begin(), W.a.begin() + cap + 2, 0.0);
  std::fill(W.b.begin(), W.b.begin() + cap + 2, 0.0);
  double* f = W.a.data() + 1;
  double* g = W.b.data() + 1;
  f[0] = 1.0;
  for (int i = 0; i < d; ++i) {
    const double p = ps[i], q = 1.0 - p;
    const int top = std::min(i + 1, cap);
    for (int j = 0; j < top; ++j) g[j] = q * f[j] + p * f[j - 1];
    if (top == cap) g[cap] = f[cap] + p * f[cap - 1];
    else g[top] = p * f[top - 1];
    st.cells += static_cast<u64>(top + 1);
    std::swap(f, g);
  }
  const double gam = (2.0 * d + cap + 4) * kU * 1.01;
  double S = 0, Snext = 0;
  int e = 0;
  for (int t = cap; t >= 0; --t) {
    Snext = S;
    S += f[t];
    if (S >= eta) { e = t; break; }
  }
  if (S * (1 - gam) >= eta && (e == cap || Snext * (1 + 2 * gam) < eta)) return e;
  ++st.amb;
  std::vector<double> Sx;
  survival_dd(ps, d, Sx);
  for (int t = cap; t >= 0; --t)
    if (Sx[t] >= eta) return t;
  return 0;
}


struct Problem {
  const Graph& g;
  std::vector<double> P;
  double eta;
  Problem(const Graph& gr, double et, u64 seed, int model) : g(gr), eta(et) {
    P.resize(g.adj.size());
#pragma omp parallel for schedule(dynamic, 1024)
    for (long long v = 0; v < static_cast<long long>(g.n); ++v)
      for (u64 e = g.off[v]; e < g.off[v + 1]; ++e) P[e] = edge_prob(static_cast<u32>(v), g.adj[e], seed, model);
  }
  int gather(u32 v, const std::vector<uint8_t>& present, std::vector<double>& ps) const {
    ps.clear();
    for (u64 e = g.off[v]; e < g.off[v + 1]; ++e)
      if (present[g.adj[e]]) ps.push_back(P[e]);
    return static_cast<int>(ps.size());
  }
};

static std::vector<int> initial_eta(const Problem& pr, const std::vector<uint8_t>& present, Stats& st, int threads) {
  const u32 n = pr.g.n;
  std::vector<int> e(n, 0);
  std::vector<Work> W(threads);
  std::vector<Stats> S(threads);
#pragma omp parallel for schedule(dynamic, 256) num_threads(threads)
  for (long long v = 0; v < static_cast<long long>(n); ++v) {
    const int t = omp_get_thread_num();
    const int d = pr.gather(static_cast<u32>(v), present, W[t].ps);
    e[v] = eta_degree(W[t].ps.data(), d, pr.eta, W[t], S[t]);
  }
  for (auto& s : S) { st.cells += s.cells; st.amb += s.amb; }
  st.evals += n;
  return e;
}


struct Buckets {
  std::vector<std::vector<u32>> b;
  void push(int k, u32 v) {
    if (k < 0) k = 0;
    if (static_cast<size_t>(k) >= b.size()) b.resize(k + 1);
    b[k].push_back(v);
  }
};


static std::vector<int> peel_ref(const Problem& pr, bool window, Stats& st, std::vector<u32>& order, double& t_init) {
  const Graph& g = pr.g;
  const u32 n = g.n;
  std::vector<uint8_t> present(n, 1);
  Timer ti;
  std::vector<int> e = initial_eta(pr, present, st, 1);
  t_init = ti.sec();
  Buckets B;
  for (u32 v = 0; v < n; ++v) B.push(e[v], v);
  std::vector<int> core(n, 0);
  Work W;
  order.clear();
  int level = 0;
  for (size_t k = 0; k < B.b.size(); ++k) {
    for (size_t i = 0; i < B.b[k].size(); ++i) {
      const u32 v = B.b[k][i];
      if (!present[v]) continue;
      level = std::max(level, static_cast<int>(k));
      core[v] = level;
      present[v] = 0;
      order.push_back(v);
      for (u64 a = g.off[v]; a < g.off[v + 1]; ++a) {
        const u32 u = g.adj[a];
        if (!present[u] || e[u] <= static_cast<int>(k)) continue;
        const int d = pr.gather(u, present, W.ps);
        ++st.evals;
        int ne;
        if (window) ne = eta_degree(W.ps.data(), d, pr.eta, W, st);
        else ne = check_trunc(W.ps.data(), d, e[u], pr.eta, W, st) ? e[u] : e[u] - 1;
        if (ne != e[u]) {
          e[u] = ne;
          B.push(std::max(ne, static_cast<int>(k)), u);
        }
      }
    }
  }
  return core;
}


static std::vector<int> peel_defl(const Problem& pr, Stats& st, std::vector<u32>& order, double& t_init) {
  const Graph& g = pr.g;
  const u32 n = g.n;
  std::vector<uint8_t> present(n, 1);
  Timer ti;

  std::vector<u64> base(n + 1);
  for (u32 v = 0; v <= n; ++v) base[v] = g.off[v] + 2ull * v;
  std::vector<double> pool(base[n] + 2, 0.0);
  std::vector<int> lo(n), hi(n), e(n);
  {
    Work W;
    for (u32 v = 0; v < n; ++v) {
      const int d = pr.gather(v, present, W.ps);
      double* f;
      int l, h;
      pmf_window(W.ps.data(), d, W, f, l, h, st.cells);
      double* S = pool.data() + base[v];
      double s = 0;
      for (int t = h; t >= l; --t) { s += f[t]; S[t] = s; }
      lo[v] = l; hi[v] = h;
      int ev = l - 1;
      for (int t = h; t >= l; --t)
        if (S[t] >= pr.eta) { ev = t; break; }
      e[v] = std::max(ev, 0);
    }
  }
  t_init = ti.sec();
  Buckets B;
  for (u32 v = 0; v < n; ++v) B.push(e[v], v);
  std::vector<int> core(n, 0);
  order.clear();
  int level = 0;
  std::vector<double> G;
  for (size_t k = 0; k < B.b.size(); ++k) {
    for (size_t i = 0; i < B.b[k].size(); ++i) {
      const u32 v = B.b[k][i];
      if (!present[v]) continue;
      level = std::max(level, static_cast<int>(k));
      core[v] = level;
      present[v] = 0;
      order.push_back(v);
      for (u64 a = g.off[v]; a < g.off[v + 1]; ++a) {
        const u32 u = g.adj[a];
        if (!present[u]) continue;
        const double p = pr.P[a], q = 1.0 - p;
        double* S = pool.data() + base[u];
        const int l = lo[u], h = hi[u];
        G.assign(h - l + 3, 0.0);
        if (p <= 0.5) {
          G[0] = 1.0;
          for (int t = l; t <= h; ++t) G[t - l + 1] = (S[t] - p * G[t - l]) / q;
        } else {
          G[h - l + 1] = 0.0;
          for (int t = h; t > l; --t) G[t - 1 - l + 1] = (S[t] - q * G[t - l + 1]) / p;
          G[0] = 1.0;
        }
        st.cells += static_cast<u64>(h - l + 1);
        ++st.evals;
        int nl = l, nh = h;
        for (int t = l; t <= h; ++t) S[t] = G[t - l + 1];
        while (nl < nh && S[nl] >= 1.0 - kTau) ++nl;
        while (nh > nl && S[nh] <= kTau) --nh;
        lo[u] = nl; hi[u] = nh;
        if (e[u] <= static_cast<int>(k)) continue;

        int ne = e[u];
        auto Sat = [&](int t) { return t < nl ? 1.0 : (t > nh ? 0.0 : S[t]); };
        while (ne > 0 && !(Sat(ne) >= pr.eta)) --ne;
        if (ne != e[u]) {
          e[u] = ne;
          B.push(std::max(ne, static_cast<int>(k)), u);
        }
      }
    }
  }
  return core;
}


static std::vector<int> peel_lazy(const Problem& pr, int threads, Stats& st, std::vector<u32>& order, double& t_init,
                                  bool window = true) {
  const Graph& g = pr.g;
  const u32 n = g.n;
  std::vector<uint8_t> present(n, 1);
  Timer ti;
  std::vector<int> ed = initial_eta(pr, present, st, threads);
  t_init = ti.sec();
  std::vector<std::atomic<int>> rem(n);
  for (u32 v = 0; v < n; ++v) rem[v].store(0, std::memory_order_relaxed);
  std::vector<std::atomic<uint8_t>> inq(n);
  for (u32 v = 0; v < n; ++v) inq[v].store(0, std::memory_order_relaxed);
  Buckets B;
  for (u32 v = 0; v < n; ++v) B.push(ed[v], v);
  std::vector<int> core(n, 0);
  std::vector<Work> W(threads);
  std::vector<Stats> TS(threads);
  std::vector<std::vector<u32>> tl_cand(threads);
  std::vector<std::vector<std::pair<int, u32>>> tl_push(threads);
  order.clear();
  std::vector<u32> cand, exact, recomp;
  auto lb = [&](u32 v) { return ed[v] - rem[v].load(std::memory_order_relaxed); };
  for (size_t k = 0; k < B.b.size(); ++k) {
    const int L = static_cast<int>(k);
    cand.clear();
    for (u32 v : B.b[k])
      if (present[v] && lb(v) <= L && !inq[v].exchange(1)) cand.push_back(v);
    std::vector<u32>().swap(B.b[k]);
    while (!cand.empty()) {
      ++st.rounds;
      exact.clear();
      recomp.clear();
      for (u32 v : cand) {
        inq[v].store(0, std::memory_order_relaxed);
        if (!present[v]) continue;
        if (rem[v].load(std::memory_order_relaxed) == 0) {
          if (ed[v] <= L) exact.push_back(v);
          else B.push(ed[v], v);
        } else {
          recomp.push_back(v);
        }
      }
#pragma omp parallel for schedule(dynamic, 16) num_threads(threads)
      for (long long i = 0; i < static_cast<long long>(recomp.size()); ++i) {
        const int t = omp_get_thread_num();
        const u32 v = recomp[i];
        const int d = pr.gather(v, present, W[t].ps);
        ed[v] = window ? eta_degree(W[t].ps.data(), d, pr.eta, W[t], TS[t])
                       : eta_degree_trunc(W[t].ps.data(), d, ed[v], pr.eta, W[t], TS[t]);
        rem[v].store(0, std::memory_order_relaxed);
        ++TS[t].evals;
      }
      for (u32 v : recomp) {
        if (ed[v] <= L) exact.push_back(v);
        else B.push(ed[v], v);
      }
      if (exact.empty()) break;
      for (u32 v : exact) {
        present[v] = 0;
        core[v] = L;
        order.push_back(v);
      }
#pragma omp parallel for schedule(dynamic, 64) num_threads(threads)
      for (long long i = 0; i < static_cast<long long>(exact.size()); ++i) {
        const int t = omp_get_thread_num();
        const u32 v = exact[i];
        for (u64 a = g.off[v]; a < g.off[v + 1]; ++a) {
          const u32 u = g.adj[a];
          if (!present[u]) continue;
          const int r = rem[u].fetch_add(1, std::memory_order_relaxed) + 1;
          const int l = ed[u] - r;
          if (l <= L) {
            if (!inq[u].exchange(1)) tl_cand[t].push_back(u);
          } else {
            tl_push[t].push_back({l, u});
          }
        }
      }
      cand.clear();
      for (int t = 0; t < threads; ++t) {
        cand.insert(cand.end(), tl_cand[t].begin(), tl_cand[t].end());
        tl_cand[t].clear();
        for (auto& [l, u] : tl_push[t]) B.push(l, u);
        tl_push[t].clear();
      }
    }
    for (u32 v : cand) inq[v].store(0, std::memory_order_relaxed);
  }
  for (auto& s : TS) { st.cells += s.cells; st.amb += s.amb; st.evals += s.evals; }
  return core;
}





static bool verify(const Problem& pr, const std::vector<int>& core, const std::vector<u32>& order, int threads,
                   u64& bad1, u64& bad2, u64& amb) {
  const Graph& g = pr.g;
  const u32 n = g.n;
  std::vector<u32> pos(n);
  for (u32 i = 0; i < n; ++i) pos[order[i]] = i;
  bool mono = true;
  for (u32 i = 1; i < n; ++i)
    if (core[order[i]] < core[order[i - 1]]) mono = false;
  std::vector<Work> W(threads);
  std::vector<Stats> S(threads);
  std::atomic<u64> b1{0}, b2{0};
#pragma omp parallel for schedule(dynamic, 256) num_threads(threads)
  for (long long v = 0; v < static_cast<long long>(n); ++v) {
    const int t = omp_get_thread_num();
    auto& ps = W[t].ps;
    ps.clear();
    for (u64 a = g.off[v]; a < g.off[v + 1]; ++a)
      if (core[g.adj[a]] >= core[v]) ps.push_back(pr.P[a]);
    if (eta_degree(ps.data(), static_cast<int>(ps.size()), pr.eta, W[t], S[t]) < core[v]) b1++;
    ps.clear();
    for (u64 a = g.off[v]; a < g.off[v + 1]; ++a)
      if (pos[g.adj[a]] > pos[v]) ps.push_back(pr.P[a]);
    if (eta_degree(ps.data(), static_cast<int>(ps.size()), pr.eta, W[t], S[t]) > core[v]) b2++;
  }
  amb = 0;
  for (auto& s : S) amb += s.amb;
  bad1 = b1;
  bad2 = b2;
  return mono && bad1 == 0 && bad2 == 0;
}

int main(int argc, char** argv) {
  if (argc < 4) {
    std::fprintf(stderr, "usage: %s <graph.bin> <eta> <ref|refw|defl|lazy> [seed] [pmodel] [threads] [out.core]\n",
                 argv[0]);
    return 1;
  }
  const std::string path = argv[1];
  const double eta = std::atof(argv[2]);
  const std::string method = argv[3];
  const u64 seed = argc > 4 ? std::strtoull(argv[4], nullptr, 10) : 1;
  const int model = argc > 5 ? std::atoi(argv[5]) : 0;
  const int threads = argc > 6 ? std::atoi(argv[6]) : 1;
  const char* out = argc > 7 ? argv[7] : nullptr;
  omp_set_num_threads(threads);
  Timer tl;
  Graph g = load_bin(path);
  const double t_load = tl.sec();
  u32 maxdeg = 0;
  for (u32 v = 0; v < g.n; ++v) maxdeg = std::max(maxdeg, g.deg(v));
  Timer tp;
  Problem pr(g, eta, seed, model);
  const double t_prob = tp.sec();
  std::printf("graph=%s n=%u m=%llu maxdeg=%u eta=%.3f method=%s seed=%llu pmodel=%d threads=%d load=%.2fs probs=%.2fs\n",
              path.c_str(), g.n, static_cast<unsigned long long>(g.m), maxdeg, eta, method.c_str(),
              static_cast<unsigned long long>(seed), model, threads, t_load, t_prob);
  std::fflush(stdout);
  Stats st;
  std::vector<u32> order;
  std::vector<int> core;
  double t_init = 0;
  Timer tr;
  if (method == "ref") core = peel_ref(pr, false, st, order, t_init);
  else if (method == "refw") core = peel_ref(pr, true, st, order, t_init);
  else if (method == "defl") core = peel_defl(pr, st, order, t_init);
  else if (method == "lazy") core = peel_lazy(pr, threads, st, order, t_init);
  else if (method == "lazyt") core = peel_lazy(pr, threads, st, order, t_init, false);
  else { std::fprintf(stderr, "unknown method\n"); return 1; }
  const double t_run = tr.sec();
  int kmax = 0;
  u64 sum = 0, h = 1469598103934665603ULL;
  for (u32 v = 0; v < g.n; ++v) {
    kmax = std::max(kmax, core[v]);
    sum += core[v];
    h = (h ^ static_cast<u64>(core[v])) * 1099511628211ULL;
  }
  std::printf("result method=%s time=%.3fs init=%.3fs peel=%.3fs kmax=%d sum_core=%llu hash=%016llx evals=%llu "
              "cells=%.4g rounds=%llu ambiguous=%llu\n",
              method.c_str(), t_run, t_init, t_run - t_init, kmax, static_cast<unsigned long long>(sum),
              static_cast<unsigned long long>(h), static_cast<unsigned long long>(st.evals),
              static_cast<double>(st.cells), static_cast<unsigned long long>(st.rounds),
              static_cast<unsigned long long>(st.amb));
  std::fflush(stdout);
  if (out) {
    FILE* f = std::fopen(out, "wb");
    if (f) {
      std::fwrite(core.data(), sizeof(int), core.size(), f);
      std::fclose(f);
    }
  }
  if (std::getenv("UCORE_VERIFY")) {
    Timer tv;
    u64 b1 = 0, b2 = 0, amb = 0;
    const bool ok = verify(pr, core, order, threads, b1, b2, amb);
    std::printf("verify ok=%d feasible_violations=%llu order_violations=%llu ambiguous=%llu time=%.2fs\n", ok ? 1 : 0,
                static_cast<unsigned long long>(b1), static_cast<unsigned long long>(b2),
                static_cast<unsigned long long>(amb), tv.sec());
  }
  return 0;
}
