// Local test fixture only: minimal S7 handshake and byte read/write support.
const net = require('net');
const banks = new Map();
function bank(area, db) { const key=`${area}:${db}`; if(!banks.has(key)) banks.set(key,Buffer.alloc(65536)); return banks.get(key); }
bank(0x84,1).writeFloatBE(12.5,0);
bank(0x83,0).writeInt16BE(123,0);
function wrap(payload) { const h=Buffer.from([3,0,0,0,2,0xf0,0x80]); h.writeUInt16BE(h.length+payload.length,2); return Buffer.concat([h,payload]); }
function reply(req,params,data,error=0) {const h=Buffer.alloc(12);h[0]=0x32;h[1]=3;req.copy(h,4,4,6);h.writeUInt16BE(params.length,6);h.writeUInt16BE(data.length,8);h.writeUInt16BE(error,10);return wrap(Buffer.concat([h,params,data]));}
const server=net.createServer(socket=>{let pending=Buffer.alloc(0);socket.on('error',()=>{});socket.on('data',chunk=>{pending=Buffer.concat([pending,chunk]);while(pending.length>=4){const n=pending.readUInt16BE(2);if(n<7){socket.destroy();return;}if(pending.length<n)return;const p=pending.subarray(0,n);pending=pending.subarray(n);try{
if(p[5]===0xe0){const response=Buffer.from(p);response[5]=0xd0;p.copy(response,6,8,10);response.writeUInt16BE(1,8);socket.write(response);continue;}
const r=p.subarray(7), pl=r.readUInt16BE(6), params=r.subarray(10,10+pl), fn=params[0];
if(r[1]===7){socket.write(reply(r,Buffer.alloc(0),Buffer.alloc(0),0x8104));continue;}
if(fn===0xf0){socket.write(reply(r,Buffer.from([0xf0,0,0,1,0,1,1,0xe0]),Buffer.alloc(0)));continue;}
if(params.length<14){socket.write(reply(r,Buffer.alloc(0),Buffer.alloc(0),0x8104));continue;}
if(fn===4||fn===5){const size=params.readUInt16BE(6),db=params.readUInt16BE(8),area=params[10],offset=params.readUIntBE(11,3)>>>3;const mem=bank(area,area===0x84?db:0);if(offset+size>mem.length)throw Error('range');if(fn===4){const dh=Buffer.from([255,4,0,0]);dh.writeUInt16BE(size*8,2);socket.write(reply(r,Buffer.from([4,1]),Buffer.concat([dh,mem.subarray(offset,offset+size)])));}else{const data=r.subarray(10+pl+4,10+pl+4+size);data.copy(mem,offset);console.log('WRITE',area,db,offset,data.toString('hex'));socket.write(reply(r,Buffer.from([5,1]),Buffer.from([255])));}continue;}
socket.write(reply(r,Buffer.alloc(0),Buffer.alloc(0),0x8104));
}catch(e){console.log('ERROR',e.message,p.toString('hex'));socket.destroy();}}});});
const port=Number(process.argv[2]||1102);
server.listen(port,'127.0.0.1',()=>console.log('SIMULATOR READY 127.0.0.1:'+port));
setTimeout(()=>server.close(()=>process.exit()),30*60*1000).unref();
