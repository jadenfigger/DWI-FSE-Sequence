"""Build the additive v1.911 fused-train candidate from uploaded method-only v7.

Original sequence files are never modified. The fused implementation is deliberately
restricted to the validated 200/700/1000 us gradient geometry. Console compilation,
physical timing, RF calibration and actual simultaneous-axis limits are scanner-verify.
"""
from pathlib import Path
import hashlib
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ZIP = ROOT/'docs/v19/compiler_compatibility/v19_method_only_v7.zip'
OUT = ROOT/'scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppl'
V7_SHA = '6a0d222b6c8689fbdee5f4ae412c4d5df0bea10a7da99a309fabf5dfab04d828'

def replace_once(s, old, new):
    assert s.count(old) == 1, (s.count(old), old[:100])
    return s.replace(old, new, 1)

DECL = '''
    int v1911_first_dac, v1911_pre_dac, v1911_post_dac, v1911_l_end;
    long v1911_c_area, v1911_d_area, v1911_den, v1911_q;
    int v1911_i_term_end;
'''

SETUP = '''
    if ((subj_angle_x!=0)||(subj_angle_y!=0)||(subj_angle_z!=0)||
        (r_angle_var[0]!=0)||(p_angle_var[0]!=0)||(s_angle_var[0]!=0)||(phase_var!=0))
    { v19_error_code=146; goto v19_fail; }
    if ((tramp!=200)||(tdp!=700)||(tcrush!=1000)||(rfdelay!=60)||(v19_f_im!=1320))
    { v19_error_code=140; goto v19_fail; }
    v1911_c_area = (0L+crusher_saved_train)*(0L+tcrush+tramp);
    v1911_c_area = v1911_c_area + (0L+crusher_saved_train)*19200L/10000L;
    v1911_d_area = (0L+v19_d_dac)*(0L+tdp+tramp);
    v1911_d_area = v1911_d_area + (0L+v19_d_dac)*19200L/10000L;
    if ((-v1911_c_area-v1911_d_area)>21474000L)
    { v19_error_code=145; goto v19_fail; }
    v1911_den = 152992L;
    v1911_q = -v1911_c_area;
    v1911_first_dac = -((v1911_q*100L+v1911_den/2L)/v1911_den);
    v1911_q = -(v1911_c_area-v1911_d_area);
    v1911_pre_dac = -((v1911_q*100L+v1911_den/2L)/v1911_den);
    v1911_q = -(v1911_c_area+v1911_d_area);
    v1911_post_dac = -((v1911_q*100L+v1911_den/2L)/v1911_den);
    if ((v1911_first_dac<crusher_saved_train)||(v1911_pre_dac<crusher_saved_train)||
        (v1911_post_dac<crusher_saved_train)||(v1911_first_dac>=0)||
        (v1911_pre_dac>=0)||(v1911_post_dac>=0))
    { v19_error_code=141; goto v19_fail; }
    v1911_q = (0L+v1911_first_dac)*v1911_den-v1911_c_area*100L;
    if (v1911_q<0L) v1911_q=-v1911_q;
    if (v1911_q>(-v1911_d_area)/100L)
    { v19_error_code=142; goto v19_fail; }
    v1911_q = (0L+v1911_pre_dac)*v1911_den-(v1911_c_area-v1911_d_area)*100L;
    if (v1911_q<0L) v1911_q=-v1911_q;
    if (v1911_q>(-v1911_d_area)/100L)
    { v19_error_code=142; goto v19_fail; }
    v1911_q = (0L+v1911_post_dac)*v1911_den-(v1911_c_area+v1911_d_area)*100L;
    if (v1911_q<0L) v1911_q=-v1911_q;
    if (v1911_q>(-v1911_d_area)/100L)
    { v19_error_code=142; goto v19_fail; }
'''

TRAIN = '''v19_echo_loop:
    waittimer(v19_wait_next);
    starttimer();
    MR3040_Start(CHANNEL_S);
    if (use_pdd>0) userout(pdd_tx_mask);
    gp_mul = get_gp_order(current_view+echo_cnt);
    gp_var = (-gp_inc*gp_mul)*nav_cnt;
    waittimer(v19_i_go_im_m_lead);
    starttimer();
    NEWSHAPE_SETUP(23, v19_mul[echo_cnt])
    waittimer(v19_i_unblank);
    rfampon(0);
    if (warmup>10) delay(warmup,us);
    waittimer(v19_i_lead_m_anc);
    rfon(rf_on);
    MR3031_go();
    CREATE_MATRIX(aq_mat_sec,gs_on*v1911_post_dac,gp_on*gp_var,gr_on*gr_dp)
    MR3040_SetList(read_list,CHANNEL_R);
    MR3040_SetList(phase_list,CHANNEL_P);
    waittimer(v19_i_offl_im);
    rfon(0);
    if (use_pdd>0) userout(pdd_rx_mask);
    waittimer(v19_i_offl_im_p_post);
    starttimer();
    waittimer(v19_i_rem_im);
    starttimer();
    MR3040_Start(CHANNEL_R|CHANNEL_P);
    templ1 = IntToLong(fov_phase_deg)*IntToLong(gp_mul);
    templ1 = templ1 + IntToLong(get_gp_var_mul2(current_view_2))*IntToLong(fov_sl_phase_deg);
    phase_rec = templ1%deg_360;
    phase_rec = phase_rec*nav_cnt;
    if (gp_on==0) phase_rec=0;
    rphase(phase_rec+phase_correction);
    echo_cnt=echo_cnt+1;
    notDummy=-(disacq_cnt>=no_disacq);
    Dummy_Cycles(!notDummy);
    waittimer(v19_i_rd_a1);
    resync();
    frequency_buffer(1);
    reset_frequency();
    waittimer(v19_i_rd_a2);
    initiate(sample_period);
    starttimer();
    CREATE_MATRIX(aq_mat_sec,gs_on*v1911_pre_dac,gp_on*gp_var,gr_on*gr_dp)
    MR3040_SetList(v19_l_im,CHANNEL_S);
    templ1=phase_ang;
    total_echo_cnt=total_echo_cnt+1;
    templ2=IntToLong(total_echo_cnt);
    templ3=templ1*templ2;
    phase_correction_0=templ3%IntToLong(deg_360);
    templ5=templ2*IntToLong(remainder_phase);
    templ4=templ5/1000L;
    phase_correction_1=templ4;
    templ4=templ5%1000L;
    phase_correction_2=0;
    if (templ4>500) phase_correction_2=1;
    if (templ4<-500) phase_correction_2=-1;
    phase_correction=(phase_correction_0+phase_correction_1+phase_correction_2)%deg_360;
    waittimer(8997);
    delay32(v19_adc_mid);
    starttimer();
    delay32(10000L);
    complete();
    frequency_buffer(0);
    reset_frequency();
    phase(phase_180+phase_correction);
    if (echo_cnt<views_per_seg)
    {
        v19_wait_next=v19_i_post_b;
        goto v19_echo_loop;
    }
    waittimer(24000);
    CREATE_MATRIX(aq_mat_sec,-gs_on*v19_d_dac,gp_on*gp_var,gr_on*gr_dp)
    delay(caldelay,us);
    MR3040_SetList(v1911_l_end,CHANNEL_S);
    waittimer(28000);
    MR3040_Start(CHANNEL_S);
    waittimer(v1911_i_term_end);
    goto v19_after_train;
'''

def build():
    with zipfile.ZipFile(ZIP) as z:
        pn=next(n for n in z.namelist() if n.endswith('1.91.ppl'))
        rn=next(n for n in z.namelist() if n.endswith('1.91.ppr'))
        raw=z.read(pn); ppr=z.read(rn).decode('latin-1')
    assert hashlib.sha256(raw).hexdigest()==V7_SHA
    s=raw.decode('latin-1').replace('\r\n','\n')
    s=replace_once(s,'int v19_error_code;', 'int v19_error_code;'+DECL)
    anchor='\t\tv19_l_ex = MR3040_InitList();'
    s=replace_once(s,anchor,SETUP+'\n'+anchor)
    old='v19_l_im = MR3040_InitList();\n\t\tPOSPULSE_SEC(tcrush, clock)\n\t\tPOSPULSE(v19_f_im, clock)\n\t\tPOSPULSE_SEC(tcrush, clock)'
    new='v19_l_im = MR3040_InitList();\n\t\tPOSPULSE_SEC(1328, clock)\n\t\tPOSPULSE(v19_f_im, clock)\n\t\tPOSPULSE_SEC(1328, clock)'
    s=replace_once(s,old,new)
    s=replace_once(s,'v19_l_im = MR3040_InitList();',
                   'v1911_l_end = MR3040_InitList();\n        POSPULSE_SEC(tdp, clock)\n        v19_l_im = MR3040_InitList();')
    s=replace_once(s,'templ3 = 2L*(0L+(tcrush)) + (0L+(v19_f_im)) + 6L*v19_r;', 'templ3 = 2656L + (0L+(v19_f_im)) + 6L*v19_r;')
    s=replace_once(s,'v19_go_im = ((0L+(tcrush))+2L*v19_r + v19_r + (0L+(v19_f_im-rf_length[23]))/2L + v19_rd)*10L;', 'v19_go_im = (1328L+3L*v19_r + (0L+(v19_f_im-rf_length[23]))/2L + v19_rd)*10L;')
    s=replace_once(s,'v19_s_1 = v19_t0 + v19_esp_us/2L - v19_rd - (0L+(v19_f_im/2)) - 3L*v19_r - (0L+(tcrush));','v19_s_1 = v19_t0 + v19_esp_us/2L - v19_rd - (0L+(v19_f_im/2)) - 3L*v19_r - 1328L;')
    # R/P now run concurrently with the fused S sides, rather than after all S.
    s=replace_once(s,'v19_gap_ir = (v19_e_1 - v19_s_1 - v19_b_im)*10L - 2L*V19_ANCHOR;', '''v19_gap_ir = 200L;
        v19_rem_im = (v19_e_1-v19_s_1)*10L-v19_off_im-V19_POST_RF-V19_ANCHOR;
        if ((v19_rem_im<300L)||(v19_rem_im>V19_MAX_WAIT))
        { v19_error_code=143; goto v19_fail; }''')
    s=replace_once(s,'(v19_post_b<v19_post_a+V19_TAIL_US*10L+V19_GAP_MIN*10L)', '(v19_post_b<(10000L+(0L+(tfilter))*10L+1000L))')
    s=replace_once(s,'(v19_e_1-v19_s_1)+v19_read_len+V19_GAP_MIN+V19_TAIL_US>v19_esp_us',
                   '(v19_e_1+3L*v19_r+(0L+tdp)<v19_s_1+2656L+(0L+v19_f_im)+6L*v19_r+V19_GAP_MIN)')
    # The source minimum is tied to the full ADC flush, not merely kept samples.
    s=replace_once(s,'\t\tv19_shot_us =', '''        if ((esp!=13)||(10000L+(0L+tfilter)*10L+3000L>24000L))
        { v19_error_code=144; goto v19_fail; }
        v19_shot_us =''')
    s=replace_once(s,'\t\tv19_i_go_ex_m_lead =',
                   '        v19_shot_us = v19_shot_us + (templ1+40000L)/10L - (v19_read_len+10L+V19_TAIL_US);\n\t\tv19_i_go_ex_m_lead =')
    s=replace_once(s,'\t\tv19_i_post_b = v19_post_b;\n','\t\tv19_i_post_b = v19_post_b;\n        v1911_i_term_end = 40000L;\n')
    old='CREATE_MATRIX(v19_m_im, gs_on*v19_g_im, 0, 0)\n\t\tdelay(caldelay,us);\n\t\tCREATE_MATRIX(v19_m_im+256, gs_on*crusher_saved_train, 0, 0)'
    s=replace_once(s,old,'''CREATE_MATRIX(aq_mat,gs_on*v19_g_im,0,(gr_on*gr_undersample)*(gr_var/gr_oversample))
        delay(caldelay,us);
        CREATE_MATRIX(aq_mat_sec,gs_on*v1911_first_dac,0,gr_on*gr_dp)''')
    old='MR3040_SelectMatrix(v19_m_im);\n\t\tMR3040_SetList(v19_l_im, CHANNEL_S);\n\t\tphase(phase_180);'
    s=replace_once(s,old,old.replace('SelectMatrix(v19_m_im)','SelectMatrix(aq_mat)'))
    a=s.index('v19_echo_loop:\n'); b=s.index('v19_exit:',a)
    s=s[:a]+TRAIN+s[b:]
    s=s.replace('V191 ss-MGOT','V1911 ss-MGOT',1)
    s=s.replace('Generated by examples/build_v19_ppl.py;', 'Generated by examples/build_v1911_ppl.py;',1)
    ppr=re.sub(r'(?m)^:VAR esp, 14\s*$', ':VAR esp, 13',ppr)
    ppr=ppr.replace('FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl', 'FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppl')
    return s,ppr

def main():
    s,ppr=build()
    OUT.write_text(s,encoding='latin-1',newline='\n')
    OUT.with_suffix('.ppr').write_text(ppr,encoding='latin-1',newline='\n')
    print(OUT)

if __name__=='__main__':main()
