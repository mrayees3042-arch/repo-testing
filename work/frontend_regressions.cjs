const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('frontend/app.js','utf8');
(async()=>{
const listeners={};let resolveWrite,calls=0;
const control=name=>({disabled:false,addEventListener:(evt,fn)=>listeners[name+evt]=fn});
const context={isConnected:true,isWriteInFlight:false,writeBoolSelect:control('bool'),writeNumericInput:control('number'),btnExecuteWrite:control('write'),validateWriteInput:()=>({valid:true,value:false}),writeTagId:{value:'1'},waitForApi:async()=>({write_tag:()=>{calls++;return new Promise(r=>resolveWrite=r)}}),writeStatusMsg:{style:{}},isPollingTags:false,setTimeout,console};
vm.createContext(context);
vm.runInContext(source.slice(source.indexOf('    writeBoolSelect.addEventListener("change"'),source.indexOf('    // --- Tag Monitoring Polling Loop ---')),context);
const first=listeners.writeclick();await new Promise(setImmediate);
listeners.boolchange();assert.equal(context.btnExecuteWrite.disabled,true);
listeners.numberinput();assert.equal(context.btnExecuteWrite.disabled,true);
await listeners.writeclick();assert.equal(calls,1);
resolveWrite({success:true,message:'verified'});await first;
// Missing bridge stays pending and never resolves to fabricated operations.
let ready;const buttons=[{disabled:false,dataset:{}},{disabled:true,dataset:{}}];
const bridge={window:{addEventListener:(_,fn)=>ready=fn},document:{querySelectorAll:()=>buttons},indicator:{}};vm.createContext(bridge);
const a=source.indexOf('    let bridgeReady');const b=source.indexOf('    // --- Modal Management');
vm.runInContext(source.slice(a,b)+'\nglobalThis.wait=waitForApi;',bridge);
const pending=bridge.wait();assert.strictEqual(pending,bridge.wait());assert(buttons.every(b=>b.disabled));
const real={get_status:()=>({})};bridge.window.pywebview={api:real};ready();assert.strictEqual(await pending,real);assert.equal(buttons[0].disabled,false);assert.equal(buttons[1].disabled,true);
console.log('PASS: duplicate write blocked, input changes stay disabled, missing bridge waits, original control states restored.');
})().catch(e=>{console.error(e);process.exitCode=1});
