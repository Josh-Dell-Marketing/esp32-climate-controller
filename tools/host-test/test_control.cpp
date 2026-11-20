#include "climate_control.h"
#include "link_protocol.h"
#include <cstdio>
int fails=0;
#define CHECK(c,msg) do{ if(!(c)){printf("FAIL: %s\n",msg);fails++;} else printf("ok: %s\n",msg);}while(0)
ClimateControl c; Settings s; bool man[4]={}; uint32_t t=0;
const Status& run(float T,float H,bool ff=false,bool valid=true){ Reading r; r.temp=T;r.hum=H;r.valid=valid; t+=1000; c.update(s,r,ff,man,t); return c.status();}
int main(){
  s.compMinOffSec=0; s.compMinOnSec=0; s.mode=Mode::Auto; c.begin(0);
  auto st=run(22,50); CHECK(!st.relay[0]&&!st.relay[1]&&!st.relay[2]&&!st.relay[3],"idle at set points");
  st=run(22.6,50); CHECK(st.relay[COMPRESSOR]&&st.relay[FAN],"cool on");
  st=run(22.2,50); CHECK(st.relay[COMPRESSOR],"cool stays");
  st=run(22.0,50); CHECK(!st.relay[COMPRESSOR]&&st.relay[FAN],"cool off, fan run-on");
  st=run(21.4,50); CHECK(st.relay[HEATER],"heat on");
  st=run(22.0,50); CHECK(!st.relay[HEATER],"heat off");
  st=run(22,46); CHECK(st.relay[HUMIDIFIER],"humidify on");
  st=run(22,50); CHECK(!st.relay[HUMIDIFIER],"humidify off");
  st=run(22,54); CHECK(st.relay[COMPRESSOR]&&st.relay[HEATER],"dehum + reheat");
  st=run(22.6,54); CHECK(st.relay[COMPRESSOR]&&!st.relay[HEATER],"reheat off");
  st=run(22.0,54); CHECK(st.relay[HEATER],"reheat back on"); st=run(22.0,50); CHECK(!st.relay[COMPRESSOR]&&!st.relay[HEATER]&&st.relay[FAN],"H50 all stop, run-on");
  st=run(22.6,50,false,false); CHECK(st.sensorFault&&!st.relay[COMPRESSOR],"sensor fault");
  st=run(21.0,54); s.compMinOnSec=60;
  st=run(21.0,54); CHECK(st.relay[COMPRESSOR]&&st.relay[HEATER],"running before fan fault");
  st=run(21.0,54,true); CHECK(st.fanFault&&!st.relay[COMPRESSOR]&&!st.relay[HEATER]&&!st.relay[HUMIDIFIER]&&st.relay[FAN],"fan fault: loads off, fan on, ignores min run");
  s.mode=Mode::Off; st=run(21,54,true); t+=60000; st=run(21,54,true); CHECK(!st.relay[FAN],"fan fault in Off: fan off after run-on");
  // FanMonitor
  Settings fs; FanMonitor m; uint32_t n=1000;
  m.update(true,0,fs,n); for(int i=0;i<24;i++){n+=1000;m.update(true,0,fs,n);} CHECK(!m.fault(),"no fault before spinup+delay");
  n+=2000; m.update(true,0,fs,n); CHECK(m.fault(),"fault after spinup+delay");
  m.clear(); m.update(true,1200,fs,n+=1000); for(int i=0;i<40;i++) m.update(true,1200,fs,n+=1000); CHECK(!m.fault(),"no fault when turning");
  fs.fanFaultRpm=0; for(int i=0;i<40;i++) m.update(true,0,fs,n+=1000); CHECK(!m.fault(),"check off with rpm 0");
  // Link
  LinkSet ls{7,IT_TEMP_SET,215}; uint8_t f[128]; size_t len=linkEncode(MSG_SET,&ls,sizeof ls,f);
  LinkParser p; bool got=false; uint8_t junk[]={0x00,0xA5,0x33,0xFF}; for(auto b:junk) p.feed(b);
  for(size_t i=0;i<len;i++) got=p.feed(f[i]); LinkSet out{}; CHECK(got&&p.type()==MSG_SET&&p.get(out)&&out.value==215&&out.seq==7,"frame round trip after junk");
  f[4]^=1; got=false; for(size_t i=0;i<len;i++) got|=p.feed(f[i]); CHECK(!got,"bad CRC dropped");
  printf("%d failures, status %zu bytes, settings %zu bytes\n",fails,sizeof(LinkStatus),sizeof(LinkSettings)); return fails;
}
