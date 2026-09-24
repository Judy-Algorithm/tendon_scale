// OpenSim 4.5.2 GeometryPath lengths at the immutable base default pose.
// Extracted on the compute server, with repair_left_geometry for the left model,
// before repair_wrap_domains, exactly as personalize.prepare records original_paths.
// Left/right lengths agree within 2e-16 m; sharing these constants is not mirroring observations.
const baseHashes={right:'9a88909ca27da9397abe22599e51ae9699162bdf274f65d2a83d7b02793b24cc',left:'45c45732788afd4fcc78b89c97cf7a5da51de82dcb735d480459ee4e8770207b'};
const lengthsM={
  ECRL:.30895372899266543,ECRB:.2825830263944274,ECU:.2992125699731512,FCR:.2947694192823788,FCU:.29813949998915196,PL:.3197534769452613,
  FDSL:.383037228139054,FDSR:.39721164490999245,FDSM:.3722374835670517,FDSI:.3734649154782938,
  FDPL:.3771013839224667,FDPR:.3810990777429023,FDPM:.3880110260911347,FDPI:.39068116498998956,
  EDCL:.4055942474186704,EDCR:.41521919897236653,EDCM:.425961771453412,EDCI:.4212506730664273,EDM:.40907871562212955,EIP:.2522998649646687,
  EPL:.28697902877490433,EPB:.17961474214910805,FPL:.2654356326504047,APL:.19913960086208943,
  APB:.07610871690745516,FPB:.05762221999125328,OPP:.04606462268530999,ADPt:.06365418894434713,ADPo:.07230168646736657,
  ADM:.06547036423780739,FDM:.056316628216753664,'1stPI':.05103287085046551,'2ndPI':.05075771452570432,'3rdPI':.04633620589208361,
  '1stDI_MC1':.065178752144889,'1stDI_MC2':.061588112092798755,'2ndDI':.05478179277015831,'3rdDI':.0566528697191217,'4thDI':.056032239865446046,
  LUML:.06194146773715851,LUMR:.06972451096672035,LUMM:.07070090017843071,LUMI:.06919801334362743
};

export function tendonScaleResult(result,id){
  // Cached results already contain the exact final/reference ratio in BOTH
  // length parameters. Do not substitute fiber + slack length for GeometryPath.
  if(!baseHashes[result.hand]||result.plan?.baseModelHash!==baseHashes[result.hand]||
    result.plan?.policies?.muscleLengths!=='Final/reference path ratio from immutable base; replace intermediate Scale result')return null;
  const p=result.report?.muscleParameters?.find(row=>row.id===id);
  const base=lengthsM[id];
  if(!base||!p||![p.fiberLengthBefore,p.fiberLengthAfter,p.tendonSlackBefore,p.tendonSlackAfter].every(v=>Number.isFinite(v)&&v>0))return null;
  const ratio=p.fiberLengthAfter/p.fiberLengthBefore;
  if(Math.abs(ratio-p.tendonSlackAfter/p.tendonSlackBefore)>1e-8)return null;
  const review=(result.report.scalingQC?.romPaths?.momentArmJumpWarnings||[]).some(row=>row.muscle===id)||
    (result.report.scalingQC?.romPaths?.nonfinite||[]).some(row=>row.muscle===id);
  return {baseLengthM:base,personalLengthM:base*ratio,ratio,changePercent:100*(ratio-1),
    status:review?'需复核':Math.abs(ratio-1)<1e-6?'长度不变':'已缩放',review};
}
