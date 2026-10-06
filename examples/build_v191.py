"""Build the concrete, uncompiled ss-MGOT adaptation from the verified v18 source.

This is a source transformation, not a vendor compiler. The original timed
playback section is retained for ss_mgot_on=0. The dedicated method path uses the
actual vendor RF/gradient macros, adds MGOT storage, spoiler and re-excitation, and is
subject to the explicitly documented vendor trace/timing validation stages.
"""
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl'
TARGET = SOURCE.with_name('FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl')
BASE_HASH = '3b420376331e918b4c864e9b37937ef35fd9f49066b8d6402e44aae9da598db2'


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError(f'expected unique v18 anchor: {old[:85]!r}; got {text.count(old)}')
    return text.replace(old, new, 1)


def build():
    raw = SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != BASE_HASH:
        raise RuntimeError('v18 source hash changed')
    base = raw.decode('cp1252').replace('\r\n', '\n')
    start = base.index('/*  Selective 90 degree pulse in presence of slice select gradient */')
    finish = base.index('#ifdef POST_ETL_CRUSHER', start)
    # Dedicated playback branch copied from the actual source; unmodified legacy
    # playback below remains available as the explicitly selected v18 control.
    played = base[start:finish]
    played = played.replace('cest_loop', 'v191_cest_loop').replace('echo_loop', 'v191_echo_loop').replace('de_90_pulse', 'v191_de_90_pulse')
    played = replace_once(played, '\techo_cnt = 0;', '\tv191_preparing = 1;\n\techo_cnt = 0;')
    # Read prephaser is deliberately not started during preparation. Its original
    # list is started ONCE at imaging entrance, after the elimination.
    played = played.replace('MR3040_Start( CHANNEL_S|CHANNEL_R );', 'MR3040_Start( CHANNEL_S ); // [V192] no prep read prephaser')
    played = played.replace('MR3040_CONTINUE(CHANNEL_S|CHANNEL_R);', 'MR3040_CONTINUE(CHANNEL_S);')
    played = played.replace('if ((diff_on==1) && (total_echo_cnt == 0))', 'if (v191_preparing==1)')
    played = played.replace('if (diff_on && total_echo_cnt == 0)', 'if (v191_preparing==1)')
    played = played.replace('if(total_echo_cnt == 0)', 'if(v191_preparing==1)')
    played = replace_once(played, '\tNEWSHAPE_SETUP(rfnum, p180_mul)', '''\t// [V192-RF] prep refocus full calibration; imaging index excludes prep.
\tv191_rf_mul = p180_mul;
\tif (v191_preparing==0)
\t\tv191_rf_mul = scale(p180_mul,v191_flip_tenth[total_echo_cnt],1800);
\tNEWSHAPE_SETUP(rfnum, v191_rf_mul)''')
    endpoint = '\t\t// TE_DELAY_2\n\t}\n'
    # This appears only at the second diffusion lobe in the copied section.
    played = replace_once(played, endpoint, endpoint + '''
\tif (v191_preparing==1)
\t{
\t\t// [V192-A] before added dephasing: prep echo is at tip RF CENTER.
\t\t// Every new lobe is separate from ordinary slice selection/crushers.
\t\tMR3040_SelectMatrix(v191_d_mat);
\t\tMR3040_SetList(v191_moment_list,CHANNEL_S);
\t\tMR3040_Clock(clock);
\t\tMR3040_Start(CHANNEL_S);
\t\tdelay(v191_moment_us,us);
\t\t// [V192-B] added dephasing complete; local transverse vectors retained.
\t\tv191_gap_us=v191_prep_wait_ticks/10L;
\t\tLONGDELAY(v191_gap_us)
\t\tphase(phase_180);
\t\tMR3040_SelectMatrix(v191_tip_mat);
\t\tMR3040_SetList(v191_tip_pre_list,CHANNEL_S);
\t\tMR3040_Start(CHANNEL_S);
\t\tdelay(v191_tip_comp_us,us);
\t\tMR3040_SetList(v191_tip_list,CHANNEL_S);
#ifdef PDD
\t\tif (use_pdd>0) userout(pdd_tx_mask);
#endif
\t\tMR3040_Start(CHANNEL_S);
\t\t// [V192-TIP] transverse My retained, Mx selectively sent to Mz.
\t\t// Symmetric gradient compensation brackets the selective RF.
\t\tMR3031_RFSTART(rfnum,tsel90,p90_mul,v191_tip_rf_pred,rf_on)
#ifdef PDD
\t\tif (use_pdd>0) userout(pdd_rx_mask);
#endif
\t\tdelay(v191_tip_post_us,us);
\t\tMR3040_SetList(v191_tip_pre_list,CHANNEL_S);
\t\tMR3040_Start(CHANNEL_S);
\t\tdelay(v191_tip_comp_us,us);
\t\t// [V192-ENDPOINT] no storage spoiler, no imaging re-excitation.
\t\t// The v18 read prephaser plays once, after elimination before RF1.
\t\tMR3040_SelectMatrix(fse_mat);
\t\tMR3040_SetList(read_pre_list,CHANNEL_R);
\t\tMR3040_Start(CHANNEL_R);
\t\tMR3040_Continue(CHANNEL_R);
\t\tdelay(v191_read_pre_us,us);
\t\tv191_gap_us=v191_tip_train_ticks/10L;
\t\tLONGDELAY(v191_gap_us)
\t\tMR3040_SetList(slice_180_refocus,CHANNEL_S);
\t\tcrusher_play_mat=slice_crush;
\t\tv191_preparing=0;
\t\t// [V192-RF1] first leading crusher is C, not C-D.
\t\t// Preparation RF was not an imaging echo; both indexes remain zero.
\t\tgoto v191_echo_loop;
\t}
\t// [V192-RECALL] +D after EVERY imaging refocus, before ADC.
\tMR3040_SelectMatrix(v191_d_mat);
\tMR3040_SetList(v191_moment_list,CHANNEL_S);
\tMR3040_Start(CHANNEL_S);
\tdelay(v191_moment_us,us);
''')
    # Legacy train delay now has a separate played recall. Its reserved physical
    # duration is subtracted from the first/later RF-to-ADC gap, never TE-extended.
    played = played.replace('delay32(te_balance_bl_temp1_esp);', 'delay32(v191_adc_wait_ticks);')
    # Explicit restoration after the ADC, before the next ordinary crusher.
    # It is kept separate so first C vs later C-D bookkeeping cannot be confused.
    played = replace_once(played, '\tcomplete();\n', '''\tcomplete();
\t// [V192-RESTORE] -D follows EVERY ADC, including the final ADC.
\t// Complete the read/PE rewind before globally selecting a new matrix.
\tdelay(v191_rewind_us,us);
\tMR3040_SelectMatrix(v191_r_mat);
\tMR3040_SetList(v191_moment_list,CHANNEL_S);
\tMR3040_Start(CHANNEL_S);
\tdelay(v191_moment_us,us);
''')
    played = played.replace('templ3 = post_adc_train_ticks;', 'templ3 = v191_post_wait_ticks;')
    # Since method has no driven-equilibrium path, first/later train loop logic is
    # inherited exactly, with method-local labels.
    played += '\tgoto v191_legacy_after_train;\n'
    text = base
    text = text.replace('"c:\\smis\\seqlib\\', '"utilities\\')
    for name in ('stdfn_15.pph','var_20.pph','offst_20.pph','m3040_15.pph','m3031_15.pph','tstex_15.pph'):
        text = text.replace(f'#include "{name}"', f'#include "utilities\\{name}"')
    text = replace_once(text, '/* PARAMLIST\n', '''/* PARAMLIST
SCROLLBAR "ss-MGOT adaptation ON", "0=verified v18 control,1=ss-MGOT draft", "%d",0,1,1,1,ss_mgot_on;
EDITTEXT "ss-MGOT dephase cycles", "2 or 4 across slice", "%d",2,4,2,1,ss_mgot_cycles;
EDITTEXT "ss-MGOT nominal slice", "um; must match PPR slice", "%d",500,30000,1000,1,ss_mgot_slice_um;
EDITTEXT "ss-MGOT moment flat", "us; exact gradient raster", "%d",1000,5000,1000,1,ss_mgot_moment_flat;
''')
    text = replace_once(text, '\tint gs_rp, gr_dp, gp_dp, gp_store;', '''\tint ss_mgot_on,ss_mgot_cycles,ss_mgot_slice_um,ss_mgot_moment_flat;
\tint v191_preparing,v191_rf_mul,v191_d_dac,v191_i;
\tint v191_d_mat,v191_r_mat,v191_tip_mat,v191_tip_sec;
\tint v191_moment_list,v191_tip_list,v191_tip_pre_list;
\tint v191_moment_us,v191_tip_comp_us,v191_tip_post_us,v191_read_pre_us;
\tint v191_tip_rf_pred;
\tint v191_rewind_us;
\tint v191_flip_tenth[8];
\tlong v191_k,v191_den,v191_slice_um,v191_tip_gcomp;
\tlong v191_prep_wait_ticks,v191_tip_train_ticks;
\tlong v191_adc_wait_ticks,v191_post_wait_ticks;
\tlong v191_tail_us,v191_centre_pre_us,v191_gap_us;
\tint gs_rp, gr_dp, gp_dp, gp_store;''')
    # Guard unsupported acquisition modes BEFORE any hardware interaction.
    text = replace_once(text, '\t#include "utilities\\tstex_15.pph"', '''\t// [V192-GUARDS] Control mode retains all original v18 branches below.
\tif ((ss_mgot_on!=0)&&(ss_mgot_on!=1))
\t{ printf("ss-MGOT switch must be 0 or 1\\n"); goto end; }
\tif (ss_mgot_on==1)
\t{
\t\tif ((diff_on!=1)||(crush_independent_on!=1)||(views_per_seg!=8))
\t\t{ printf("ss-MGOT needs DWI, independent crushers, ETL8\\n"); goto end; }
\t\tif ((rfnum!=1)||(alpha!=90)||(crusher_schedule!=0)||(echoes_to_discard!=0))
\t\t{ printf("ss-MGOT draft needs RF1, 90excite, constant C, no skip\\n"); goto end; }
\t\tif ((no_slices!=1)||(no_views_2!=1)||(flow_comp_on!=0)||(dixon_on!=0)||(de_on!=0))
\t\t{ printf("ss-MGOT draft supports 2D single slice; no flow/Dixon/DE\\n"); goto end; }
\t\tif ((rec_freq!=0)||(slice_mm_10!=0)||(sat_on!=0)||(chess_on!=0)||(mtc_on!=0))
\t\t{ printf("ss-MGOT draft needs zero RX/slice shift and no presat\\n"); goto end; }
\t\tif ((gsp_lobe!=0)||(gs_comp_scale!=0)||(post_90_delay1!=0)||(phcor0!=0))
\t\t{ printf("ss-MGOT needs native slice compensation and RF phase\\n"); goto end; }
\t\tif ((gs_on!=1)||(gr_on!=1)||(gp_sl_on!=1)||(setup_mode!=0))
\t\t{ printf("ss-MGOT needs slice/read ON, setup OFF\\n"); goto end; }
\t\tif ((ss_mgot_cycles!=2)&&(ss_mgot_cycles!=4))
\t\t{ printf("ss-MGOT dephase cycles must be 2 or 4\\n"); goto end; }
\t\tif ((ss_mgot_slice_um<500)||(ss_mgot_slice_um>30000))
\t\t{ printf("ss-MGOT slice must be 500..30000 um\\n"); goto end; }
\t\tif ((ss_mgot_moment_flat<1000)||(ss_mgot_moment_flat>5000)||(tramp<100)||(tramp>1000)||(tramp%10!=0))
\t\t{ printf("ss-MGOT invalid moment/ramp duration\\n"); goto end; }
\t\tif ((IntToLong(ss_mgot_moment_flat)*50L)%IntToLong(tramp)!=0L)
\t\t{ printf("ss-MGOT moment not on gradient raster\\n"); goto end; }
\t\tv191_i=0;
v191_offset_guard:
\t\tif ((fov_slice_off[v191_i]!=0)||(fov_read_off[v191_i]!=0)||(fov_phase_off[v191_i]!=0))
\t\t{ printf("ss-MGOT draft needs centered FOV offsets\\n"); goto end; }
\t\tv191_i=v191_i+1;
\t\tif (v191_i<no_slices) goto v191_offset_guard;
\t\tif ((rfcal<1)||(rfcal>1023)||(p180_scale<1)||(p180_scale>300)||((IntToLong(rfcal)*IntToLong(p180_scale))/100L>2047L))
\t\t{ printf("ss-MGOT RF calibration exceeds DAC ceiling\\n"); goto end; }
\t\tv191_flip_tenth[0]=1422; v191_flip_tenth[1]=949;
\t\tv191_flip_tenth[2]=692; v191_flip_tenth[3]=630;
\t\tv191_flip_tenth[4]=602; v191_flip_tenth[5]=600;
\t\tv191_flip_tenth[6]=600; v191_flip_tenth[7]=600;
\t}
\t#include "utilities\\tstex_15.pph"''')
    # RF and gradient geometry exist before new lists are built.
    text = replace_once(text, '\tMR3040_SetListAddress(0);', '''\tMR3040_SetListAddress(0);
\tif (ss_mgot_on==1)
\t{
\t\t// Actual PARSETUP slice, not nominal label alone; <=1% geometry error.
\t\tif ((gs_var==0)||(grad_varl<1L)||((IntToLong(gs_var)*grad_varl)/100L==0L))
\t\t{ printf("ss-MGOT invalid slice/gradient calibration\\n"); goto end; }
\t\tv191_slice_um=(-32768L*10700L)/((IntToLong(gs_var)*grad_varl)/100L);
\t\tif ((v191_slice_um<0L)||(v191_slice_um<ss_mgot_slice_um*99L/100L)||(v191_slice_um>ss_mgot_slice_um*101L/100L))
\t\t{ printf("ss-MGOT nominal slice disagrees with PPR selector\\n"); goto end; }
\t\tv191_k=(IntToLong(ss_mgot_cycles)*1000000L)/IntToLong(ss_mgot_slice_um);
\t\tv191_den=(grad_varl*IntToLong(ss_mgot_moment_flat+tramp)+500L)/1000L;
\t\tif (v191_den<1L) { printf("ss-MGOT invalid gradient calibration\\n"); goto end; }
\t\ttempl1=(v191_k*32767L+v191_den/2L)/v191_den;
\t\tif ((templ1<1L)||(templ1>32767L)||(templ1>crusher_max_dac))
\t\t{ printf("ss-MGOT moment exceeds logical DAC ceiling\\n"); goto end; }
\t\tif (templ1*100L>IntToLong(crusher_slew_dac_100us)*IntToLong(tramp))
\t\t{ printf("ss-MGOT moment exceeds slew ceiling\\n"); goto end; }
\t\tv191_d_dac=templ1;
\t\tv191_moment_us=ss_mgot_moment_flat+2*tramp;
\t\tv191_tip_comp_us=tref+2*tramp;
\t\tv191_read_pre_us=tref+4*tramp;
\t\tv191_rewind_us=2*tramp+tdp+rfdelay+tfilter+100;
\t\tv191_tip_post_us=tramp+crush_rf_pad/2;
\t\tv191_tip_rf_pred=tramp+crush_rf_pad/2;
\t\t// Existing sinc is linear phase; symmetric half-area compensation.
\t\tv191_tip_gcomp=(IntToLong(gs_var_rescale)*IntToLong(crush_rf_flat+tramp))/2L/IntToLong(tref+tramp);
\t\tif ((v191_tip_gcomp<-32767L)||(v191_tip_gcomp>32767L))
\t\t{ printf("ss-MGOT tip slice compensation DAC overflow\\n"); goto end; }
\t\tv191_moment_list=MR3040_InitList();
\t\tPOSPULSE(ss_mgot_moment_flat,clock)
\t\tv191_tip_pre_list=MR3040_InitList();
\t\tNEGPULSE_SEC(tref,clock)
\t\tv191_tip_list=MR3040_InitList();
\t\tPOSPULSE(crush_rf_flat,clock)
\t\tv191_d_mat=40; v191_r_mat=41; v191_tip_mat=42; v191_tip_sec=298;
\t}''')
    # New timing budgets must be evaluated before validator's early return.
    timing = '''
\tif (ss_mgot_on==1)
\t{
\t\t// [V192-TIMING] nominal source-derived timing, vendor trace pending.
\t\t// Timing costs below include explicit 200-us instruction reserve per
\t\t// new transition; expose these estimates, do not call measured centers.
\t\tv191_tail_us=IntToLong(tsel180/2+tramp+tcrush1_play-rfdelay)+extra_delta_us/10L+sm_delta_us+diff_tramp;
\t\tv191_centre_pre_us=IntToLong(v191_tip_rf_pred+tsel90/2);
\t\tv191_prep_wait_ticks=(IntToLong(te)*500L-v191_tail_us-v191_moment_us-v191_tip_comp_us-v191_centre_pre_us-200L)*10L;
\t\tv191_tip_train_ticks=(IntToLong(esp)*500L-IntToLong(tsel90/2+v191_tip_post_us+v191_tip_comp_us+v191_read_pre_us+tramp+tcrush_play+rfdelay+tsel180/2)-200L)*10L;
\t\tv191_adc_wait_ticks=te_balance_bl_temp1_esp-IntToLong(v191_moment_us+200)*10L;
\t\tv191_post_wait_ticks=(te_balance_bl_temp2+te_balance_bl_esp+IntToLong(crush_post_pad-crush_pre_pad-v191_rewind_us-v191_moment_us-200))*10L;
\t\tif ((v191_prep_wait_ticks<1500L)||(v191_tip_train_ticks<1500L)||(v191_adc_wait_ticks<=25L)||(v191_post_wait_ticks<=1000L))
\t\t{ printf("ss-MGOT TE/ESP too short for tip or recall/restore\\n"); goto end; }
\t\tprintf("ss-MGOT nominal prepTE=%d ms firstTE=%ld us ESP=%d ms\\n",te,(IntToLong(te)+IntToLong(esp))*1000L,esp);
\t\tprintf("ss-MGOT timing is source estimate; compile/event trace required\\n");
\t}
'''
    text = replace_once(text, '/*  Calculate phase increment following each 180 degree pulse */', timing + '\n/*  Calculate phase increment following each 180 degree pulse */')
    text = replace_once(text, '\ttr_min = templ1 + templ2 + templ3;', '\tif (ss_mgot_on==1) templ1=templ1+IntToLong(esp)*1000L; // one prep echo plus N imaging echoes\n\ttr_min = templ1 + templ2 + templ3;')
    matrices = '''
\tif (ss_mgot_on==1)
\t{
\t\t// New dedicated matrices are never updated while they are playing.
\t\tMR3040_SelectMatrix(ss_mat);
\t\tpos_index=0;
\t\tCREATE_MATRIX(v191_d_mat,v191_d_dac,0,0)
\t\tdelay(caldelay,us);
\t\tCREATE_MATRIX(v191_r_mat,-v191_d_dac,0,0)
\t\tdelay(caldelay,us);
\t\tCREATE_MATRIX(v191_tip_mat,gs_var_rescale,0,0)
\t\tdelay(caldelay,us);
\t\tCREATE_MATRIX(v191_tip_sec,v191_tip_gcomp,0,0)
\t\tdelay(caldelay,us);
\t}
'''
    # The supported method is one static slice/orientation; matrices are created
    # once under the zero-gradient setup matrix, before validator's early return.
    text = text.replace('#ifdef VALIDATOR\n\tif (validate==1)', matrices + '\n#ifdef VALIDATOR\n\tif (validate==1)', 1)
    text = replace_once(text, '/*  Selective 90 degree pulse in presence of slice select gradient */', '\tif (ss_mgot_on==1) goto v191_method_start;\n\n/*  Selective 90 degree pulse in presence of slice select gradient */')
    # Place the shared tail label at the actual playback post-ETL section, not its
    # earlier timing-accounting section.
    legacy_finish = text.index('#ifdef POST_ETL_CRUSHER', text.index('/*  Selective 90 degree pulse'))
    text = text[:legacy_finish] + 'v191_legacy_after_train:\n' + text[legacy_finish:]
    text = replace_once(text, '\nend:\n', '\n\tgoto end;\n\n// [V192-METHOD-BEGIN] Concrete scanner macro event path; uncompiled adaptation.\nv191_method_start:\n' + played + '\n// [V192-METHOD-END]\nend:\n')
    header = '''/* V192 SS-MGOT SCANNER-PROTOCOL ADAPTATION -- CONCRETE SOURCE, UNCOMPILED.
   Actual v18 retained as ss_mgot_on=0 control; method path owns separate labels.
   ss-MGOT retains MG transverse and eliminates unwanted quadrature onto Mz.
   Existing measured-library sinc and asymptotic flip completion are disclosed
   approximations, not a Gibbons reference reproduction. Do not deploy here.
   New timing instruction reserves are estimates pending compiler/event trace.
   See docs/v19/v191_implementation.md and generated event ledger. */
'''
    TARGET.write_bytes((header + text).replace('\n','\r\n').encode('cp1252'))
    ppr = SOURCE.with_suffix('.ppr').read_bytes().decode('cp1252').replace('\r\n','\n')
    ppr = ppr.replace(':PPL FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl', ':PPL FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl',1)
    ppr = ppr.replace(':VIEWS_PER_SEGMENT views_per_seg, 2', ':VIEWS_PER_SEGMENT views_per_seg, 8',1)
    ppr = ppr.replace(':NO_VIEWS no_views, 4', ':NO_VIEWS no_views, 128',1)
    ppr = ppr.replace(':VAR te, 36', ':VAR te, 64',1)
    ppr = ppr.replace(':FOV_SLICE_OFF fov_slice_off, 3, -480\n, 0, 480', ':FOV_SLICE_OFF fov_slice_off, 3, 0\n, 0, 0',1)
    ppr = ppr.replace(':FOV_OFFSETS 3\n, 0, 0, -1.2\n, 0, 0, 0\n, 0, 0, 1.2', ':FOV_OFFSETS 3\n, 0, 0, 0\n, 0, 0, 0\n, 0, 0, 0',1)
    ppr += ':VAR ss_mgot_on, 1\n:VAR ss_mgot_cycles, 2\n:VAR ss_mgot_slice_um, 1000\n:VAR ss_mgot_moment_flat, 1000\n'
    TARGET.with_suffix('.ppr').write_bytes(ppr.replace('\n','\r\n').encode('cp1252'))
    print(f'Built concrete uncompiled {TARGET.name}; original v18 hash unchanged')


if __name__ == '__main__':
    build()
