% Newly designed research samples, not Gibbons' original coefficients.
outdir=fileparts(mfilename('fullpath'));
addpath(genpath(fullfile(outdir,'toolbox','Spectral-Spatial-RF-Pulse-Design-master')));
gamma=4257.6; dt=10e-6;
names={'slr_prep90_3p2ms','slr_prep180_3p2ms','slr_elim90_3p2ms'};
types={'ex','se','sat'};
for idx=1:3
    rf=dzrf(320,3.55,types{idx},'ls',0.005,0.01);
    b1=rf(:)/(2*pi*gamma*dt)*1e-4; % radians/sample -> Tesla
    gz=ones(320,1)*(3.55/0.0032/0.018)/(gamma*1e4); % 18-mm slab
    if idx==3, gz=gz*3; end % 6-mm elimination slice
    t=((0:319)'+0.5)*dt;
    writematrix([t real(b1) imag(b1) gz],fullfile(outdir,[names{idx} '.csv']));
    fprintf('%s peakB1=%.9g uT, Gz=%.9g mT/m\n',names{idx},max(abs(b1))*1e6,gz(1)*1e3);
end
% Explicit Hamming window is a declared substitute for unspecified imaging window.
np=120; duration=1.2e-3;
u=((0:np-1)'+0.5)/np-0.5;
w=sinc(1.54*u).*(0.54+0.46*cos(2*pi*u));
b1=w/(4*gamma*1e4*dt*sum(w));
gz=ones(np,1)*(1.54/duration/0.006)/(gamma*1e4);
t=((0:np-1)'+0.5)*dt;
writematrix([t b1 zeros(np,1) gz],fullfile(outdir,'windowed_reexc90_1p2ms.csv'));
fprintf('windowed_reexc90_1p2ms peakB1=%.9g uT Gz=%.9g mT/m\n',max(b1)*1e6,gz(1)*1e3);
