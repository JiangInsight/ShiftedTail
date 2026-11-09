#pragma once
#include <algorithm>
#include <cstdint>
#include <limits>
#include <utility>
#include <vector>


class PeelQueue {
 public:
  using Entry=std::pair<double,uint32_t>;
  PeelQueue(size_t n,bool indexed): indexed_(indexed),pos_(indexed?n:0,absent) {
    data_.reserve(n+16);
  }
  void add_initial(Entry e) { data_.push_back(e); }
  void build() {
    if (!indexed_) { std::make_heap(data_.begin(),data_.end(),after); return; }
    for (uint32_t i=0;i<data_.size();++i) pos_[data_[i].second]=i;
    if (data_.size()>1)
      for (size_t p=(data_.size()-2)/4+1;p>0;--p) down(p-1,data_[p-1]);
  }
  bool empty() const { return data_.empty(); }
  Entry pop() {
    if (!indexed_) {
      std::pop_heap(data_.begin(),data_.end(),after);
      Entry e=data_.back();data_.pop_back();return e;
    }
    Entry first=data_.front(),last=data_.back();data_.pop_back();pos_[first.second]=absent;
    if (!data_.empty()) down(0,last);
    return first;
  }
  void set(Entry e) {
    if (!indexed_) {
      data_.push_back(e);std::push_heap(data_.begin(),data_.end(),after);return;
    }
    size_t i=pos_[e.second];
    if (i==absent) { i=data_.size();data_.push_back(e); up(i,e); }
    else if (e.first<data_[i].first) up(i,e);
    else if (e.first>data_[i].first) down(i,e);
  }
 private:
  static constexpr uint32_t absent=std::numeric_limits<uint32_t>::max();
  static bool after(const Entry& a,const Entry& b) { return a.first>b.first; }
  void place(size_t i,Entry e) { data_[i]=e;pos_[e.second]=static_cast<uint32_t>(i); }
  void up(size_t i,Entry e) {
    while (i) {
      size_t p=(i-1)/4;
      if (data_[p].first<=e.first) break;
      place(i,data_[p]);i=p;
    }
    place(i,e);
  }
  void down(size_t i,Entry e) {
    for (size_t first=4*i+1;first<data_.size();first=4*i+1) {
      size_t best=first;
      const size_t end=std::min(data_.size(),first+4);
      for (size_t j=first+1;j<end;++j) if (data_[j].first<data_[best].first) best=j;
      if (data_[best].first>=e.first) break;
      place(i,data_[best]);i=best;
    }
    place(i,e);
  }
  bool indexed_;
  std::vector<Entry> data_;
  std::vector<uint32_t> pos_;
};
