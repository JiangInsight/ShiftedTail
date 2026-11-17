#include "../verified_tail.hpp"
#include <cstdio>
#if defined(__SSE2__) || defined(_M_X64)
#include <xmmintrin.h>
#endif
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>
int main(int argc,char** argv){
    if(argc==2){
        if(std::string(argv[1])=="wrong-round")std::fesetround(FE_UPWARD);
#if defined(__SSE2__) || defined(_M_X64)
        else if(std::string(argv[1])=="flush-zero")_mm_setcsr(_mm_getcsr() | (1u<<15));
        else if(std::string(argv[1])=="denormals-zero")_mm_setcsr(_mm_getcsr() | (1u<<6));
#endif
        else return 2;
    }
    if(!checked_pb::supported_environment())return 4;
    int k,n;std::string token;
    checked_pb::Workspace a;
    while(std::cin>>k>>n){
        std::vector<double> p(n);
        for(double& x:p){std::cin>>token;x=std::strtod(token.c_str(),nullptr);}
        checked_pb::Effort e;
        auto i=checked_pb::evaluate(p,k,a,e);
        std::printf("%.17g %.17g %zu %llu\n",i.lo,i.hi,e.factors,(unsigned long long)e.cells);
    }
}
