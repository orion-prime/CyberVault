import {useEffect,useState} from "react";
const API = import.meta.env.VITE_API_URL || "";
const TOKEN_KEY="cybervault_access_token";
function apiFetch(url,options={}){
 const token=localStorage.getItem(TOKEN_KEY);
 const headers={...(options.headers||{})};
 if(token)headers.Authorization=`Bearer ${token}`;
 return fetch(url,{...options,headers});
}
export default function App(){
 const [token,setToken]=useState(()=>localStorage.getItem(TOKEN_KEY)||""),[loginUser,setLoginUser]=useState(""),[loginPassword,setLoginPassword]=useState(""),[items,setItems]=useState([]),[file,setFile]=useState(null),[candidates,setCandidates]=useState({}),[results,setResults]=useState({}),[msg,setMsg]=useState(""),[busy,setBusy]=useState(false),[custody,setCustody]=useState({});
 async function signIn(e){
  e.preventDefault();
  try{
   const r=await fetch(`${API}/api/auth/login`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:loginUser,password:loginPassword})});
   const d=await r.json();if(!r.ok)throw Error(d.detail||"Login failed");
   localStorage.setItem(TOKEN_KEY,d.access_token);setToken(d.access_token);setLoginPassword("");setMsg("Signed in successfully.");
  }catch(err){setMsg(err.message)}
 }
 function signOut(){localStorage.removeItem(TOKEN_KEY);setToken("");setItems([]);setResults({});setCustody({});setMsg("You have signed out.");}
 async function refresh(){const r=await apiFetch(API+"/api/evidence");if(r.ok)setItems(await r.json());}
 useEffect(()=>{if(token)refresh().catch(()=>setMsg("Session expired or backend unavailable. Please sign in again."));},[token]);
 async function collect(e){e.preventDefault();if(!file)return;setBusy(true);try{let f=new FormData();f.append("file",file);let r=await apiFetch(API+"/api/evidence",{method:"POST",body:f}),d=await r.json();if(!r.ok)throw Error(d.detail||"Upload failed");setMsg(`Collected ${d.original_filename}; evidence ID ${d.id}.`);e.target.reset();setFile(null);await refresh();}catch(x){setMsg(x.message)}finally{setBusy(false)}}

 async function loadCustody(item){
  setBusy(true);
  try{
   const [eventsResponse,verifyResponse]=await Promise.all([
    apiFetch(`${API}/api/evidence/${item.id}/custody`),
    apiFetch(`${API}/api/evidence/${item.id}/custody/verify`)
   ]);
   const events=await eventsResponse.json(),integrity=await verifyResponse.json();
   if(!eventsResponse.ok)throw Error(events.detail||"Could not load custody history");
   if(!verifyResponse.ok)throw Error(integrity.detail||"Could not verify custody history");
   setCustody(s=>({...s,[item.id]:{events,integrity}}));
   setMsg(integrity.valid?"Custody history loaded; hash chain valid.":"Custody integrity check failed.");
  }catch(e){setMsg(e.message)}finally{setBusy(false)}
 }
 async function downloadReport(item){
  const analysis=results[item.id];
  if(!analysis){setMsg("Run an analysis before generating a report.");return;}
  setBusy(true);
  try{
   const r=await apiFetch(`${API}/api/evidence/${item.id}/report`,{
    method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(analysis)
   });
   if(!r.ok){let d=await r.json().catch(()=>({}));throw Error(d.detail||"Report generation failed");}
   const blob=await r.blob(),url=URL.createObjectURL(blob),a=document.createElement("a");
   a.href=url;a.download=`CyberVault_EV-${String(item.id).padStart(4,"0")}_forensic_report.pdf`;
   document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url);
   setMsg("Forensic PDF report generated.");
  }catch(e){setMsg(e.message)}finally{setBusy(false)}
 }
 async function run(item,mode){let candidate=candidates[item.id];if(!candidate){setMsg("Choose a candidate file first.");return;}setBusy(true);try{let f=new FormData();f.append("file",candidate);let url=mode==="semantic"?`${API}/api/evidence/${item.id}/analyze-pdf`:mode==="image"?`${API}/api/evidence/${item.id}/analyze-image`:`${API}/api/evidence/${item.id}/verify`;let r=await apiFetch(url,{method:"POST",body:f}),d=await r.json();if(!r.ok)throw Error(d.detail||"Request failed");setResults(s=>({...s,[item.id]:{...d,mode}}));setMsg(mode==="semantic"?"PDF semantic analysis completed.":mode==="image"?"Image analysis completed.":`Hash result: ${d.status}`);}catch(x){setMsg(x.message)}finally{setBusy(false)}}
 if(!token)return <main className="auth-wrap"><section className="auth-card"><div className="logo">⬡ <span>CYBERVAULT</span></div><p className="eyebrow">SECURE INVESTIGATOR ACCESS</p><h1>Welcome back.</h1><p className="hint">Sign in to access protected forensic evidence and investigation records.</p><form onSubmit={signIn}><label>USERNAME</label><input className="auth-input" autoComplete="username" value={loginUser} onChange={e=>setLoginUser(e.target.value)} required/><label>PASSWORD</label><input className="auth-input" type="password" autoComplete="current-password" value={loginPassword} onChange={e=>setLoginPassword(e.target.value)} required/><button type="submit">Sign in securely</button></form>{msg&&<p className="notice">{msg}</p>}<p className="hint">Accounts are provisioned by the system administrator.</p></section></main>;
 return <main className="wrap"><header><div className="logo">⬡ <span>CYBERVAULT</span></div><div className="header-actions"><small>SECURE INVESTIGATOR WORKSPACE</small><button className="soft" onClick={signOut}>Sign out</button></div></header>
 <section className="hero"><p>FORENSIC EVIDENCE WORKSPACE</p><h1>Beyond the hash.<br/><i>Understand the change.</i></h1><div>Collect evidence, verify integrity, investigate PDF and image differences, and review its custody history.</div></section>
 {msg&&<div className="notice">{msg}</div>}
 <section className="panel"><div className="eyebrow">01 / COLLECTION</div><h2>Register original evidence</h2><form onSubmit={collect}><input type="file" required onChange={e=>setFile(e.target.files?.[0]||null)}/><button disabled={busy||!file}>Collect & hash</button></form><p className="hint">Original file is preserved in local storage and its SHA-256 baseline is recorded.</p></section>
 <section className="panel"><div className="eyebrow">02 / INVESTIGATION</div><h2>Evidence register <small>{items.length} records</small></h2>
 {!items.length?<p className="empty">No evidence registered yet.</p>:items.map(item=><article className="record" key={item.id}><div className="row"><b>{item.original_filename}</b><small>EV-{String(item.id).padStart(4,"0")}</small></div><label>BASELINE SHA-256</label><code>{item.sha256}</code><div className="actions"><input type="file" onChange={e=>setCandidates(s=>({...s,[item.id]:e.target.files?.[0]||null}))}/><button className="soft" disabled={busy} onClick={()=>run(item,"hash")}>Verify hash</button><button disabled={busy} onClick={()=>run(item,"semantic")}>Analyze PDF</button><button className="soft" disabled={busy} onClick={()=>loadCustody(item)}>Custody history</button>{[".jpg",".jpeg",".png",".tif",".tiff",".bmp",".webp"].includes(item.original_filename.toLowerCase().slice(item.original_filename.lastIndexOf(".")))&&<button disabled={busy} onClick={()=>run(item,"image")}>Analyze Image</button>}</div>
 {results[item.id]&&<div className="result"><div className="report-action"><button className="soft" disabled={busy} onClick={()=>downloadReport(item)}>Download forensic PDF report</button></div><div className="row"><b>{results[item.id].mode!=="hash"?results[item.id].classification:results[item.id].status}</b><strong className={"sev "+(results[item.id].severity||"").toLowerCase()}>{results[item.id].severity||""}</strong></div><p>{results[item.id].explanation||results[item.id].message}</p>
 {results[item.id].visual_comparison&&<div className="visual-forensics"><h3>VISUAL FORENSIC COMPARISON</h3><p className="hint">{results[item.id].visual_comparison.preview_note}</p><div className="visual-grid"><figure><img src={results[item.id].visual_comparison.side_by_side_data_url} alt="Original and candidate image side by side"/><figcaption>Original (left) · Candidate (right)</figcaption></figure><figure><img src={results[item.id].visual_comparison.heatmap_data_url} alt="Pixel difference heatmap"/><figcaption>Difference heatmap · brighter areas show larger pixel differences</figcaption></figure><figure><img src={results[item.id].visual_comparison.overlay_data_url} alt="Blended image overlay"/><figcaption>50/50 blended overlay</figcaption></figure></div></div>}
 {results[item.id].similarity_ssim!==undefined&&<div className="image-metrics"><h3>Image comparison metrics</h3><div className="metric-grid"><div><small>SSIM similarity</small><b>{results[item.id].similarity_ssim}</b></div><div><small>Changed pixel ratio</small><b>{(results[item.id].changed_pixel_ratio*100).toFixed(2)}%</b></div><div><small>Mean pixel difference</small><b>{results[item.id].mean_absolute_pixel_difference}</b></div></div><p>Dimensions: {results[item.id].dimensions.original.join(" × ")} → {results[item.id].dimensions.uploaded.join(" × ")}</p><p>Formats: {results[item.id].formats.original} → {results[item.id].formats.uploaded}</p>{results[item.id].ela_mean_original!==null&&results[item.id].ela_mean_original!==undefined&&<p>JPEG ELA mean: {results[item.id].ela_mean_original} → {results[item.id].ela_mean_uploaded}</p>}</div>}
 {results[item.id].exif_changes?.length>0&&<><h3>EXIF metadata differences</h3>{results[item.id].exif_changes.map((c,i)=><p key={i}>{c.field}: {String(c.original??"—")} → {String(c.uploaded??"—")}</p>)}</>}
 {results[item.id].number_changes?.length>0&&<><h3>Numeric token differences</h3>{results[item.id].number_changes.map((c,i)=><p key={i}><code>{JSON.stringify(c)}</code></p>)}</>}
 {results[item.id].trust_score!==undefined&&<div className="scorebox"><div><span className="score-label">CYBERVAULT TRUST SCORE</span><strong className={"score-number "+(results[item.id].risk_band||"").toLowerCase()}>{results[item.id].trust_score}<small>/100</small></strong></div><div><b>{results[item.id].risk_band} RISK</b><p className="hint">Rule-based triage score; not a probability of authenticity.</p></div></div>}
 {results[item.id].forensic_explanation&&<div className="explanation"><div className="explanation-title"><b>{results[item.id].forensic_explanation.report_title}</b><span>{results[item.id].forensic_explanation.review_priority.replaceAll("_"," ")}</span></div><p>{results[item.id].forensic_explanation.summary}</p><h3>Investigator findings</h3>{results[item.id].forensic_explanation.findings.map((finding,i)=><div className="finding" key={i}><b>{finding.type.replaceAll("_"," ")}</b><p>{finding.meaning}</p>{finding.original_value!==undefined&&<p><code>{String(finding.original_value)} → {String(finding.uploaded_value)}</code></p>}{finding.changed_fields?.length>0&&<p>Changed fields: {finding.changed_fields.join(", ")}</p>}</div>)}<h3>Recommended actions</h3><ol>{results[item.id].forensic_explanation.recommendations.map((action,i)=><li key={i}>{action}</li>)}</ol><details><summary>Report limitations</summary><ul>{results[item.id].forensic_explanation.limitations.map((limitation,i)=><li key={i}>{limitation}</li>)}</ul></details></div>}
 {results[item.id].score_breakdown&&<details className="score-details"><summary>How was this score calculated?</summary><pre>{JSON.stringify(results[item.id].score_breakdown,null,2)}</pre></details>}
 {results[item.id].metadata_changes?.length>0&&<><h3>Metadata differences</h3>{results[item.id].metadata_changes.map((c,i)=><p key={i}>{c.field}: {String(c.original??"—")} → {String(c.uploaded??"—")}</p>)}</>}
 {results[item.id].text_diff?.length>0&&<><h3>Extracted text diff</h3><pre>{results[item.id].text_diff.join("\n")}</pre></>}
 {results[item.id].limitations&&<p className="hint">{results[item.id].limitations.join(" ")}</p>}</div>}
 {custody[item.id]&&<div className="custody-panel"><div className="row"><b>CHAIN OF CUSTODY</b><strong className={custody[item.id].integrity.valid?"chain-valid":"chain-invalid"}>{custody[item.id].integrity.valid?"INTEGRITY VERIFIED":"INTEGRITY CHECK FAILED"}</strong></div><p className="hint">{custody[item.id].integrity.message} · {custody[item.id].integrity.checked_events} events checked</p>{custody[item.id].events.length===0?<p className="hint">No custody events recorded yet. New actions will be recorded from this module onward.</p>:<ol className="custody-list">{custody[item.id].events.map(ev=><li key={ev.id}><div><b>{ev.event_type.replaceAll("_"," ")}</b><small>{new Date(ev.occurred_at).toLocaleString()} · {ev.actor}</small></div><p>{ev.details}</p><code>Event hash: {ev.event_hash}</code></li>)}</ol>}</div>}</article>)}</section>
 <footer>Prototype only · A hash mismatch or semantic flag is not proof of fraud. Human review is required.</footer></main>
}
