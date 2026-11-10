v {xschem version=3.4.6 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
N -200 0 -20 0 {lab=in}
N 20 -60 20 -30 {lab=out}
N 20 0 40 0 {lab=0}
N 20 30 20 60 {lab=0}
C {symbols/nfet_03v3.sym} 0 0 0 0 {name=M1
L=0.5u
W=10u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {devices/res.sym} 20 -90 0 0 {name=R1 value=10k footprint=1206 device=resistor m=1}
C {devices/vsource.sym} -200 30 0 0 {name=Vin value=0.9 savecurrent=false}
C {devices/vsource.sym} 120 -60 0 0 {name=Vdd value=3.3 savecurrent=false}
C {devices/lab_pin.sym} 20 -120 1 0 {name=p1 sig_type=std_logic lab=vdd}
C {devices/lab_pin.sym} 120 -90 1 0 {name=p2 sig_type=std_logic lab=vdd}
C {devices/lab_pin.sym} 120 -30 3 0 {name=p3 sig_type=std_logic lab=0}
C {devices/lab_pin.sym} -200 60 3 0 {name=p4 sig_type=std_logic lab=0}
C {devices/lab_pin.sym} 20 60 3 0 {name=p5 sig_type=std_logic lab=0}
C {devices/lab_pin.sym} 40 0 2 0 {name=p6 sig_type=std_logic lab=0}
C {devices/lab_pin.sym} 20 -50 2 0 {name=p7 sig_type=std_logic lab=out}
C {devices/opin.sym} 80 -50 0 0 {name=p8 lab=out}
C {devices/code_shown.sym} -200 -200 0 0 {name=MODELS only_toplevel=false
value="
.param sw_stat_global=0 sw_stat_mismatch=0 mc_skew=3 res_mc_skew=3 cap_mc_skew=3 fnoicor=0
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice res_typical
.temp 27
.control
op
print v(out) i(Vdd)
.endc
"}
