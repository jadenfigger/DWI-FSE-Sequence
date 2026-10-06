% Research-only design using author-owned toolbox; no scanner deployment.
% Gibbons 2018 MRM 79:3036 specifications. Newly designed, NOT original samples.
outdir = fileparts(mfilename('fullpath'));
if ~exist('candidate_duration_s','var'), candidate_duration_s=5.64e-3; end
if ~exist('candidate_prefix','var'), candidate_prefix='candidate'; end
tbdir = fullfile(outdir,'toolbox','Spectral-Spatial-RF-Pulse-Design-master');
addpath(genpath(tbdir));
addpath(outdir);
ss_opt([]);
ss_globals;
SS_TS = 4e-6; % version-pinned toolbox exposes sampling time as a global
ss_opt({'Nucleus','Hydrogen','Max Grad',2.29,'Max Slew',15, ...
    'Max B1',0.226,'Max Duration',candidate_duration_s, ...
    'Verse Fraction',1,'SLR',1,'Spect Correct',1, ...
    'Spect Correct Reg',0.001,'Num Lobe Iters',5,'Num Fs Test',100});
% The ex pulse and its inverse require independent basis-transfer validation;
% excitation magnitude alone cannot certify selective transverse-to-Mz storage.
angles = asin([0.05,0.995]);
[gz,rf,fs] = ss_design_batch(1,3.55,[0.005,0.01], ...
    [-549,-306,-128,128],angles,[0.01,0.005], ...
    'ex','ls','max','Flyback Whole',0,0,1);
save(fullfile(outdir,[candidate_prefix '.mat']),'gz','rf','fs');
dt=4e-6;
t=((0:numel(rf)-1)+0.5)'*dt;
writematrix([t,real(rf(:))*1e-4,imag(rf(:))*1e-4,gz(:)*0.01], ...
    fullfile(outdir,[candidate_prefix '_t_B1realT_B1imagT_GzTm.csv']));
fprintf('Duration %.9g s; spectral sampling %.9g Hz; peak B1 %.9g G; peak G %.9g G/cm\n', ...
    numel(rf)*dt,fs,max(abs(rf)),max(abs(gz)));
