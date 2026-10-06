"""Build the concrete, uncompiled Alsop adaptation from the verified v18 source.

This is a source transformation, not a vendor compiler. The original timed
playback section is retained for alsop_on=0. The dedicated method path uses the
actual vendor RF/gradient macros, adds no MGOT storage/re-excitation, and is
subject to the explicitly documented vendor trace/timing validation stages.
"""
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl'
TARGET = SOURCE.with_name('FSE_dwi_CPMG_non_CPMG_twoTE-1.92.ppl')
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
    played = played.replace('cest_loop', 'v192_cest_loop').replace('echo_loop', 'v192_echo_loop').replace('de_90_pulse', 'v192_de_90_pulse')
    played = replace_once(played, '\techo_cnt = 0;', '\tv192_preparing = 1;\n\techo_cnt = 0;')
    # Read prephaser is deliberately not started during preparation. Its original
    # list is started ONCE at imaging entrance, after the elimination.
    played = played.replace('MR3040_Start( CHANNEL_S|CHANNEL_R );', 'MR3040_Start( CHANNEL_S ); // [V192] no prep read prephaser')
    played = played.replace('MR3040_CONTINUE(CHANNEL_S|CHANNEL_R);', 'MR3040_CONTINUE(CHANNEL_S);')
    played = played.replace('if ((diff_on==1) && (total_echo_cnt == 0))', 'if (v192_preparing==1)')
    played = played.replace('if (diff_on && total_echo_cnt == 0)', 'if (v192_preparing==1)')
    played = played.replace('if(total_echo_cnt == 0)', 'if(v192_preparing==1)')
    played = replace_once(played, '\tNEWSHAPE_SETUP(rfnum, p180_mul)', '\tNEWSHAPE_SETUP(v192_rf_slot, v192_rf_mul)')
    played = replace_once(played, 'v192_echo_loop:\n\tMR3040_SelectMatrix(crusher_play_mat);', '''v192_echo_loop:
\t// [V192-RF-SETUP] New selection arithmetic is inside a real padded window.
\tstarttimer();
\tv192_rf_slot=19; v192_rf_mul=p180_mul;
\tif (v192_preparing==0)
\t{ v192_rf_slot=21; v192_rf_mul=scale(v192_image_mul,v192_flip_tenth[total_echo_cnt],1800); }
\tMR3040_SelectMatrix(crusher_play_mat);
\tV192_CLOSE_SETUP
''')
    endpoint = '\t\t// TE_DELAY_2\n\t}\n'
    # This appears only at the second diffusion lobe in the copied section.
    played = replace_once(played, endpoint, endpoint + '''
\tif (v192_preparing==1)
\t{
\t\t// [V192-A] before added dephasing: prep echo is at tip RF CENTER.
\t\t// Every new lobe is separate from ordinary slice selection/crushers.
\t\tV192_GRAD(v192_d_mat,v192_moment_list,CHANNEL_S,v192_moment_us)
\t\t// [V192-B] added dephasing complete; local transverse vectors retained.
\t\tv192_gap_us=v192_prep_wait_ticks/10L;
\t\tLONGDELAY(v192_gap_us)
\t\tV192_GRAD(v192_tip_mat,v192_tip_pre_list,CHANNEL_S,v192_tip_comp_us)
\t\tstarttimer();
\t\tphase(phase_180);
\t\tMR3040_SelectMatrix(v192_tip_mat);
\t\tMR3040_SetList(v192_tip_list,CHANNEL_S);
\t\tv192_window_ticks=(crush_rf_flat+2*tramp+500)*10;
\t\tV192_CLOSE_SETUP
\t\tstarttimer();
\t\tMR3040_Start(CHANNEL_S);
\t\t// [V192-TIP] transverse My retained, Mx selectively sent to Mz.
\t\t// Symmetric gradient compensation brackets the selective RF.
\t\tMR3031_RFSTART(20,tsel90,v192_tip_mul,v192_tip_rf_pred,rf_on)
\t\tV192_CLOSE_PLAY
\t\tV192_GRAD(v192_tip_mat,v192_tip_pre_list,CHANNEL_S,v192_tip_comp_us)
\t\t// [V192-ENDPOINT] no storage spoiler, no imaging re-excitation.
\t\t// The v18 read prephaser plays once, after elimination before RF1.
\t\tstarttimer();
\t\tMR3040_SelectMatrix(fse_mat);
\t\tMR3040_SetList(read_pre_list,CHANNEL_R);
\t\tv192_window_ticks=(v192_read_pre_us+500)*10;
\t\tV192_CLOSE_SETUP
\t\tstarttimer();
\t\tMR3040_Start(CHANNEL_R);
\t\tMR3040_Continue(CHANNEL_R);
\t\tV192_CLOSE_PLAY
\t\tv192_gap_us=v192_tip_train_ticks/10L;
\t\tLONGDELAY(v192_gap_us)
\t\tMR3040_SetList(slice_180_refocus,CHANNEL_S);
\t\tcrusher_play_mat=slice_crush;
\t\tv192_preparing=0;
\t\t// [V192-RF1] first leading crusher is C, not C-D.
\t\t// Preparation RF was not an imaging echo; both indexes remain zero.
\t\tgoto v192_echo_loop;
\t}
\t// [V192-RECALL] +D after EVERY imaging refocus, before ADC.
\tV192_GRAD(v192_d_mat,v192_moment_list,CHANNEL_S,v192_moment_us)
''')
    # Legacy train delay now has a separate played recall. Its reserved physical
    # duration is subtracted from the first/later RF-to-ADC gap, never TE-extended.
    played = played.replace('delay32(te_balance_bl_temp1_esp);', 'delay32(v192_adc_wait_ticks);')
    # Explicit restoration after the ADC, before the next ordinary crusher.
    # It is kept separate so first C vs later C-D bookkeeping cannot be confused.
    played = replace_once(played, '\tcomplete();\n', '''\tcomplete();
\t// [V192-RESTORE] -D follows EVERY ADC, including the final ADC.
\t// Complete the read/PE rewind before globally selecting a new matrix.
\tdelay(v192_rewind_us,us);
\tV192_GRAD(v192_r_mat,v192_moment_list,CHANNEL_S,v192_moment_us)
''')
    played = played.replace('templ3 = post_adc_train_ticks;', 'templ3 = v192_post_wait_ticks;')
    played = played.replace('templ3 = post_adc_base_ticks;', 'templ3 = v192_final_wait_ticks;')
    # Since method has no driven-equilibrium path, first/later train loop logic is
    # inherited exactly, with method-local labels.
    played += '\tgoto v192_legacy_after_train;\n'
    text = base
    text = text.replace('"c:\\smis\\seqlib\\', '"utilities\\')
    for name in ('stdfn_15.pph','var_20.pph','offst_20.pph','m3040_15.pph','m3031_15.pph','tstex_15.pph'):
        text = text.replace(f'#include "{name}"', f'#include "utilities\\{name}"')
    text = replace_once(text, '/* PARAMLIST\n', '''/* PARAMLIST
SCROLLBAR "Alsop adaptation ON", "0=verified v18 control,1=Alsop draft", "%d",0,1,1,1,alsop_on;
EDITTEXT "Alsop dephase cycles", "2 or 4 across slice", "%d",2,4,2,1,alsop_cycles;
EDITTEXT "Alsop nominal slice", "um; must match PPR slice", "%d",500,30000,1000,1,alsop_slice_um;
EDITTEXT "Alsop moment flat", "us; exact gradient raster", "%d",1000,5000,1000,1,alsop_moment_flat;
''')
    text = replace_once(text, '\tint gs_rp, gr_dp, gp_dp, gp_store;', '''\tint alsop_on,alsop_cycles,alsop_slice_um,alsop_moment_flat;
\tint v192_preparing,v192_rf_mul,v192_d_dac,v192_i;
\tint v192_d_mat,v192_r_mat,v192_tip_mat,v192_tip_sec;
\tint v192_moment_list,v192_tip_list,v192_tip_pre_list;
\tint v192_moment_us,v192_tip_comp_us,v192_tip_post_us,v192_read_pre_us;
\tint v192_tip_rf_pred;
\tint v192_rewind_us;
\tint v192_flip_tenth[8];
\tlong v192_k,v192_den,v192_slice_um,v192_tip_gcomp;
\tlong v192_prep_wait_ticks,v192_tip_train_ticks;
\tlong v192_adc_wait_ticks,v192_post_wait_ticks;
\tlong v192_tail_us,v192_centre_pre_us,v192_gap_us;
\tint gs_rp, gr_dp, gp_dp, gp_store;''')
    # Guard unsupported acquisition modes BEFORE any hardware interaction.
    text = replace_once(text, '\t#include "utilities\\tstex_15.pph"', '''\t// [V192-GUARDS] Control mode retains all original v18 branches below.
\tif ((alsop_on!=0)&&(alsop_on!=1))
\t{ printf("Alsop switch must be 0 or 1\\n"); goto end; }
\tif (alsop_on==1)
\t{
\t\tif ((diff_on!=1)||(crush_independent_on!=1)||(views_per_seg!=8))
\t\t{ printf("Alsop needs DWI, independent crushers, ETL8\\n"); goto end; }
\t\tif ((rfnum!=1)||(alpha!=90)||(crusher_schedule!=0)||(echoes_to_discard!=0))
\t\t{ printf("Alsop draft needs RF1, 90excite, constant C, no skip\\n"); goto end; }
\t\tif ((no_slices!=1)||(no_views_2!=1)||(flow_comp_on!=0)||(dixon_on!=0)||(de_on!=0))
\t\t{ printf("Alsop draft supports 2D single slice; no flow/Dixon/DE\\n"); goto end; }
\t\tif ((rec_freq!=0)||(slice_mm_10!=0)||(sat_on!=0)||(chess_on!=0)||(mtc_on!=0))
\t\t{ printf("Alsop draft needs zero RX/slice shift and no presat\\n"); goto end; }
\t\tif ((gsp_lobe!=0)||(gs_comp_scale!=0)||(post_90_delay1!=0)||(phcor0!=0))
\t\t{ printf("Alsop needs native slice compensation and RF phase\\n"); goto end; }
\t\tif ((gs_on!=1)||(gr_on!=1)||(gp_sl_on!=1)||(setup_mode!=0))
\t\t{ printf("Alsop needs slice/read ON, setup OFF\\n"); goto end; }
\t\tif ((alsop_cycles!=2)&&(alsop_cycles!=4))
\t\t{ printf("Alsop dephase cycles must be 2 or 4\\n"); goto end; }
\t\tif ((alsop_slice_um<500)||(alsop_slice_um>30000))
\t\t{ printf("Alsop slice must be 500..30000 um\\n"); goto end; }
\t\tif ((alsop_moment_flat<1000)||(alsop_moment_flat>5000)||(tramp<100)||(tramp>1000)||(tramp%10!=0))
\t\t{ printf("Alsop invalid moment/ramp duration\\n"); goto end; }
\t\tif ((IntToLong(alsop_moment_flat)*50L)%IntToLong(tramp)!=0L)
\t\t{ printf("Alsop moment not on gradient raster\\n"); goto end; }
\t\tv192_i=0;
v192_offset_guard:
\t\tif ((fov_slice_off[v192_i]!=0)||(fov_read_off[v192_i]!=0)||(fov_phase_off[v192_i]!=0))
\t\t{ printf("Alsop draft needs centered FOV offsets\\n"); goto end; }
\t\tv192_i=v192_i+1;
\t\tif (v192_i<no_slices) goto v192_offset_guard;
\t\tif ((rfcal<1)||(rfcal>1023)||(p180_scale<1)||(p180_scale>300)||((IntToLong(rfcal)*IntToLong(p180_scale))/100L>2047L))
\t\t{ printf("Alsop RF calibration exceeds DAC ceiling\\n"); goto end; }
\t\tv192_flip_tenth[0]=1422; v192_flip_tenth[1]=949;
\t\tv192_flip_tenth[2]=692; v192_flip_tenth[3]=630;
\t\tv192_flip_tenth[4]=602; v192_flip_tenth[5]=600;
\t\tv192_flip_tenth[6]=600; v192_flip_tenth[7]=600;
\t}
\t#include "utilities\\tstex_15.pph"''')
    # RF and gradient geometry exist before new lists are built.
    text = replace_once(text, '\tMR3040_SetListAddress(0);', '''\tMR3040_SetListAddress(0);
\tif (alsop_on==1)
\t{
\t\t// Actual PARSETUP slice, not nominal label alone; <=1% geometry error.
\t\tif ((gs_var==0)||(grad_varl<1L)||((IntToLong(gs_var)*grad_varl)/100L==0L))
\t\t{ printf("Alsop invalid slice/gradient calibration\\n"); goto end; }
\t\tv192_slice_um=(-32768L*10700L)/((IntToLong(gs_var)*grad_varl)/100L);
\t\tif ((v192_slice_um<0L)||(v192_slice_um<alsop_slice_um*99L/100L)||(v192_slice_um>alsop_slice_um*101L/100L))
\t\t{ printf("Alsop nominal slice disagrees with PPR selector\\n"); goto end; }
\t\tv192_k=(IntToLong(alsop_cycles)*1000000L)/IntToLong(alsop_slice_um);
\t\tv192_den=(grad_varl*IntToLong(alsop_moment_flat+tramp)+500L)/1000L;
\t\tif (v192_den<1L) { printf("Alsop invalid gradient calibration\\n"); goto end; }
\t\ttempl1=(v192_k*32767L+v192_den/2L)/v192_den;
\t\tif ((templ1<1L)||(templ1>32767L)||(templ1>crusher_max_dac))
\t\t{ printf("Alsop moment exceeds logical DAC ceiling\\n"); goto end; }
\t\tif (templ1*100L>IntToLong(crusher_slew_dac_100us)*IntToLong(tramp))
\t\t{ printf("Alsop moment exceeds slew ceiling\\n"); goto end; }
\t\tv192_d_dac=templ1;
\t\tv192_moment_us=alsop_moment_flat+2*tramp;
\t\tv192_tip_comp_us=tref+2*tramp;
\t\tv192_read_pre_us=tref+4*tramp;
\t\tv192_rewind_us=2*tramp+tdp+rfdelay+tfilter+100;
\t\tv192_tip_post_us=tramp+crush_rf_pad/2;
\t\tv192_tip_rf_pred=tramp+crush_rf_pad/2;
\t\t// Existing sinc is linear phase; symmetric half-area compensation.
\t\tv192_tip_gcomp=(IntToLong(gs_var_rescale)*IntToLong(crush_rf_flat+tramp))/2L/IntToLong(tref+tramp);
\t\tif ((v192_tip_gcomp<-32767L)||(v192_tip_gcomp>32767L))
\t\t{ printf("Alsop tip slice compensation DAC overflow\\n"); goto end; }
\t\tv192_moment_list=MR3040_InitList();
\t\tPOSPULSE(alsop_moment_flat,clock)
\t\tv192_tip_pre_list=MR3040_InitList();
\t\tNEGPULSE_SEC(tref,clock)
\t\tv192_tip_list=MR3040_InitList();
\t\tPOSPULSE(crush_rf_flat,clock)
\t\tv192_d_mat=40; v192_r_mat=41; v192_tip_mat=42; v192_tip_sec=298;
\t}''')
    # New timing budgets must be evaluated before validator's early return.
    timing = '''
\tif (alsop_on==1)
\t{
\t\t// [V192-TIMING] nominal source-derived timing, vendor trace pending.
\t\t// Timing costs below include explicit 200-us instruction reserve per
\t\t// new transition; expose these estimates, do not call measured centers.
\t\tv192_tail_us=IntToLong(tsel180/2+tramp+tcrush1_play-rfdelay)+extra_delta_us/10L+sm_delta_us+diff_tramp;
\t\tv192_centre_pre_us=IntToLong(v192_tip_rf_pred+tsel90/2);
\t\tv192_prep_wait_ticks=(IntToLong(te)*500L-v192_tail_us-v192_moment_us-v192_tip_comp_us-v192_centre_pre_us-200L)*10L;
\t\tv192_tip_train_ticks=(IntToLong(esp)*500L-IntToLong(tsel90/2+v192_tip_post_us+v192_tip_comp_us+v192_read_pre_us+tramp+tcrush_play+rfdelay+tsel180/2)-200L)*10L;
\t\tv192_adc_wait_ticks=te_balance_bl_temp1_esp-IntToLong(v192_moment_us+200)*10L;
\t\tv192_post_wait_ticks=(te_balance_bl_temp2+te_balance_bl_esp+IntToLong(crush_post_pad-crush_pre_pad-v192_rewind_us-v192_moment_us-200))*10L;
\t\tif ((v192_prep_wait_ticks<1500L)||(v192_tip_train_ticks<1500L)||(v192_adc_wait_ticks<=25L)||(v192_post_wait_ticks<=1000L))
\t\t{ printf("Alsop TE/ESP too short for tip or recall/restore\\n"); goto end; }
\t\tprintf("Alsop nominal prepTE=%d ms firstTE=%ld us ESP=%d ms\\n",te,(IntToLong(te)+IntToLong(esp))*1000L,esp);
\t\tprintf("Alsop timing is source estimate; compile/event trace required\\n");
\t}
'''
    text = replace_once(text, '/*  Calculate phase increment following each 180 degree pulse */', timing + '\n/*  Calculate phase increment following each 180 degree pulse */')
    text = replace_once(text, '\ttr_min = templ1 + templ2 + templ3;', '\tif (alsop_on==1) templ1=templ1+IntToLong(esp)*1000L; // one prep echo plus N imaging echoes\n\ttr_min = templ1 + templ2 + templ3;')
    matrices = '''
\tif (alsop_on==1)
\t{
\t\t// New dedicated matrices are never updated while they are playing.
\t\tMR3040_SelectMatrix(ss_mat);
\t\tpos_index=0;
\t\tCREATE_MATRIX(v192_d_mat,v192_d_dac,0,0)
\t\tdelay(caldelay,us);
\t\tCREATE_MATRIX(v192_r_mat,-v192_d_dac,0,0)
\t\tdelay(caldelay,us);
\t\tCREATE_MATRIX(v192_tip_mat,gs_var_rescale,0,0)
\t\tdelay(caldelay,us);
\t\tCREATE_MATRIX(v192_tip_sec,v192_tip_gcomp,0,0)
\t\tdelay(caldelay,us);
\t}
'''
    # The supported method is one static slice/orientation; matrices are created
    # once under the zero-gradient setup matrix, before validator's early return.
    text = text.replace('#ifdef VALIDATOR\n\tif (validate==1)', matrices + '\n#ifdef VALIDATOR\n\tif (validate==1)', 1)
    text = replace_once(text, '/*  Selective 90 degree pulse in presence of slice select gradient */', '\tif (alsop_on==1) goto v192_method_start;\n\n/*  Selective 90 degree pulse in presence of slice select gradient */')
    # Place the shared tail label at the actual playback post-ETL section, not its
    # earlier timing-accounting section.
    legacy_finish = text.index('#ifdef POST_ETL_CRUSHER', text.index('/*  Selective 90 degree pulse'))
    text = text[:legacy_finish] + 'v192_legacy_after_train:\n' + text[legacy_finish:]
    text = replace_once(text, '\nend:\n', '\n\tgoto end;\n\n// [V192-METHOD-BEGIN] Concrete scanner macro event path; uncompiled adaptation.\nv192_method_start:\n' + played + '\n// [V192-METHOD-END]\nend:\n')
    header = '''/* V192 ALSOP SCANNER-PROTOCOL ADAPTATION -- CONCRETE SOURCE, UNCOMPILED.
   Actual v18 retained as alsop_on=0 control; method path owns separate labels.
   Alsop retains MG transverse and eliminates unwanted quadrature onto Mz.
   Existing measured-library sinc and asymptotic flip completion are disclosed
   approximations, not a Gibbons reference reproduction. Do not deploy here.
   New timing instruction reserves are estimates pending compiler/event trace.
   See docs/v19/v192_implementation.md and generated event ledger. */
'''
    TARGET.write_bytes((header + text).replace('\n','\r\n').encode('cp1252'))
    ppr = SOURCE.with_suffix('.ppr').read_bytes().decode('cp1252').replace('\r\n','\n')
    ppr = ppr.replace(':PPL FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl', ':PPL FSE_dwi_CPMG_non_CPMG_twoTE-1.92.ppl',1)
    ppr = ppr.replace(':VIEWS_PER_SEGMENT views_per_seg, 2', ':VIEWS_PER_SEGMENT views_per_seg, 8',1)
    ppr = ppr.replace(':NO_VIEWS no_views, 4', ':NO_VIEWS no_views, 128',1)
    ppr = ppr.replace(':VAR te, 36', ':VAR te, 64',1)
    ppr = ppr.replace(':FOV_SLICE_OFF fov_slice_off, 3, -480\n, 0, 480', ':FOV_SLICE_OFF fov_slice_off, 3, 0\n, 0, 0',1)
    ppr = ppr.replace(':FOV_OFFSETS 3\n, 0, 0, -1.2\n, 0, 0, 0\n, 0, 0, 1.2', ':FOV_OFFSETS 3\n, 0, 0, 0\n, 0, 0, 0\n, 0, 0, 0',1)
    ppr += ':VAR alsop_on, 1\n:VAR alsop_cycles, 2\n:VAR alsop_slice_um, 1000\n:VAR alsop_moment_flat, 1000\n'
    TARGET.with_suffix('.ppr').write_bytes(ppr.replace('\n','\r\n').encode('cp1252'))
    print(f'Built concrete uncompiled {TARGET.name}; original v18 hash unchanged')


if __name__ == '__main__':
    build()
