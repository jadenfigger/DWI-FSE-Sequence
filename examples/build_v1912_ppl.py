"""Reproducible additive v1.912 build from immutable scanner v1.911 bytes.

These files are source-model candidates; vendor compilation and scanner timing
remain required. Fused-lobe shape, DAC lattice, diffusion selection and RF assets
are inherited exactly.
"""
from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppl'
OUT = ROOT / 'scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.912.ppl'
BASE_SHA = '716478bb357ba1479e6cc8fcc18c1085e44b3c78ecf1bdf32bb561b171838682'
PPR_SHA = 'b2976e7464367a7aa6b6b8e04765cc04a3fd85c0d2ec64c9c9a57963bf9635c2'


def once(s, old, new):
    assert s.count(old) == 1, (s.count(old), old[:100])
    return s.replace(old, new, 1)


def build():
    raw = BASE.read_bytes()
    ppr_raw = BASE.with_suffix('.ppr').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == BASE_SHA
    assert hashlib.sha256(ppr_raw).hexdigest() == PPR_SHA
    s = raw.decode('latin-1').replace('\r\n', '\n')
    ppr = ppr_raw.decode('latin-1').replace('\r\n', '\n')
    s = once(s, 'int v19_error_code;', '''int v19_error_code;
    int v1912_echoes, v1912_flip, v1912_i, v1912_j;
    int v1912_freq[4], v1912_corr[5];
    long v1912_min_esp, v1912_need, v1912_width, v1912_sep;
    long v1912_acc, v1912_q, v1912_pos, v1912_span, v1912_centre;''')
    s = once(s, 'SCROLLBAR "Navigator?","1=yes","%d",0,1,0,1,nav_on;',
             'SCROLLBAR "Navigator?","0=off, 1=per volume, 2=per shot","%d",0,2,0,1,nav_on;')
    s = once(s, '\tif (PE_order != 2){', '''    if ((nav_on<0)||(nav_on>2))
    { v19_error_code=150; goto v19_fail; }
    if (nav_on==2)
    {
        if ((PE_order!=1)||(views_per_seg<2)||(no_views%views_per_seg!=0)||
            (no_views<2*views_per_seg))
        { v19_error_code=151; goto v19_fail; }
        views_per_seg=views_per_seg-1;
        no_views=(no_views/(views_per_seg+1))*views_per_seg;
    }
\tif (PE_order != 2){''')
    s = s.replace('if(nav_on==1)', 'if(nav_on>=1)')
    s = s.replace('if (nav_on==1)', 'if (nav_on>=1)')
    s = s.replace('if (nav_on) {', 'if (nav_on>=1) {')
    # v19_post_b binds the next fused-lobe start after the ADC/filter flush;
    # v19_rem_im binds RF-to-readout separation; first_wait binds re-excitation.
    # Each bound is affine in ESP/2, so subtract its present slack to obtain
    # the actual protocol's minimum, then round up to the console ms lattice.
    anchor = '\t\tif ((v19_gap_x1<V19_GAP_MIN*10L)'
    idx = s.index(anchor)
    s = s[:idx] + '''        v1912_min_esp=v19_esp_us-2L*(v19_post_b-
            (10000L+(0L+tfilter)*10L+1000L))/10L;
        v1912_need=v19_esp_us-2L*(v19_rem_im-300L)/10L;
        if (v1912_need>v1912_min_esp) v1912_min_esp=v1912_need;
        v1912_need=v19_esp_us-2L*(v19_s_1-v19_len-V19_GAP_MIN);
        if (v1912_need>v1912_min_esp) v1912_min_esp=v1912_need;
        v1912_need=v19_esp_us-2L*(v19_e_1+3L*v19_r+(0L+tdp)-
            v19_s_1-2656L-(0L+v19_f_im)-6L*v19_r-V19_GAP_MIN);
        if (v1912_need>v1912_min_esp) v1912_min_esp=v1912_need;
        v1912_min_esp=(v1912_min_esp+999L)/1000L;
        if ((0L+esp)<v1912_min_esp)
        {
            printf("V1912 minimum ESP=%ld ms\\n",v1912_min_esp);
            v19_error_code=147; goto v19_fail;
        }
''' + s[idx:]
    # This guard is a genuine timer target range, not a fixed dwell/ESP lock.
    old = '''        if ((v19_rem_im<300L)||(v19_rem_im>V19_MAX_WAIT))
        { v19_error_code=143; goto v19_fail; }'''
    s = once(s, old, '')
    s = once(s, '(v19_post_b>V19_MAX_WAIT)||(v19_rd_a2>V19_MAX_WAIT)||(v19_df_wait<1000L))',
             '(v19_post_b>V19_MAX_WAIT)||(v19_rd_a2>V19_MAX_WAIT)||(v19_df_wait<1000L)||(v19_rem_im>V19_MAX_WAIT))')
    s = once(s, '''        if ((esp!=13)||(10000L+(0L+tfilter)*10L+3000L>24000L))
        { v19_error_code=144; goto v19_fail; }''', '''        if (10000L+(0L+tfilter)*10L+3000L>24000L)
        { v19_error_code=144; goto v19_fail; }
        v1912_echoes=views_per_seg;
        if (nav_on==2) v1912_echoes=v1912_echoes+1;''')
    s = once(s, '(0L+(views_per_seg-1))*v19_esp_us',
             '(0L+(v1912_echoes-1))*v19_esp_us')
    # Select each slab with its own played gradient. The common shift cancels
    # in the pairwise spacing test. Orientation locks cover every slice.
    s = once(s, '''\t\tif ((no_slices!=1)||(slice_mm_10!=0)||(fov_slice_off[0]!=0))
\t\t{ v19_error_code=3; goto v19_fail; }''', '')
    s = once(s, '    v1911_c_area = (0L+crusher_saved_train)*(0L+tcrush+tramp);', '''    v1912_i=0;
v1912_angle_check:
    if ((r_angle_var[v1912_i]!=0)||(p_angle_var[v1912_i]!=0)||
        (s_angle_var[v1912_i]!=0))
    { v19_error_code=146; goto v19_fail; }
    v1912_i=v1912_i+1;
    if (v1912_i<no_slices) goto v1912_angle_check;
    v1912_q=35060690L/(0L+v19_gabs);
    v1912_width=(v1912_q/grad_varl)*400L+
        ((v1912_q%grad_varl)*400L+grad_varl-1L)/grad_varl;
    v1912_need=v19_slab_pml;
    if (v19_tip_pml>v1912_need) v1912_need=v19_tip_pml;
    v1912_sep=(v1912_width*(v1912_need+1000L)+1999L)/2000L;
    v1912_sep=v1912_sep+(v1912_width*750L+999L)/1000L;
    v1912_i=0;
v1912_slice_check:
    v1912_j=v1912_i+1;
v1912_pair_check:
    if (v1912_j<no_slices)
    {
        v1912_need=(0L+fov_slice_off[v1912_i])-fov_slice_off[v1912_j];
        if (v1912_need<0L) v1912_need=-v1912_need;
        if (v1912_need<v1912_sep)
        {
            printf("V1912 minimum slice separation=%ld units\\n",v1912_sep);
            v19_error_code=148; goto v19_fail;
        }
        v1912_j=v1912_j+1;
        goto v1912_pair_check;
    }
    v1912_i=v1912_i+1;
    if (v1912_i<no_slices-1) goto v1912_slice_check;
    v1911_c_area = (0L+crusher_saved_train)*(0L+tcrush+tramp);''')
    s = once(s, '''    gp_mul = get_gp_order(current_view+echo_cnt);
    gp_var = (-gp_inc*gp_mul)*nav_cnt;''', '''    gp_mul = get_gp_order(current_view+echo_cnt);
    v1912_flip=echo_cnt;
    if (echo_cnt==views_per_seg)
    {
        gp_mul=0;
        v1912_flip=views_per_seg-1;
    }
    gp_var = (-gp_inc*gp_mul)*nav_cnt;''')
    s = once(s, 'NEWSHAPE_SETUP(23, v19_mul[echo_cnt])',
             'NEWSHAPE_SETUP(23, v19_mul[v1912_flip])')
    s = once(s, 'if (echo_cnt<views_per_seg)\n', 'if (echo_cnt<v1912_echoes)\n')
    # Mirror the sampled negative prephaser exactly in mode 2. The matrix P
    # sign changes after acquisition starts, while P is zero between lobes.
    # This removes the inherited positive-frame rounding imbalance without
    # changing modes 0/1, RF/readout timing or the requested imaging PE grid.
    s = once(s, '''\tphase_list = MR3040_InitList();
\tNEGPULSE_SEC(tdp, clock)
\tDELAY(tramp, clock, "0_max")
\tDELAY(tacq_int, clock, "0_max")
\tDELAY(tramp, clock, "0_max")
\tPOSPULSE_SEC(tdp, clock)''', '''\tphase_list = MR3040_InitList();
\tNEGPULSE_SEC(tdp, clock)
\tDELAY(tramp, clock, "0_max")
\tDELAY(tacq_int, clock, "0_max")
\tDELAY(tramp, clock, "0_max")
    if (nav_on==2) { NEGPULSE_SEC(tdp, clock) }
    else { POSPULSE_SEC(tdp, clock) }''')
    s = once(s, '''    CREATE_MATRIX(aq_mat_sec,gs_on*v1911_pre_dac,gp_on*gp_var,gr_on*gr_dp)''',
             '''    if (nav_on==2) gp_var=-gp_var;
    CREATE_MATRIX(aq_mat_sec,gs_on*v1911_pre_dac,gp_on*gp_var,gr_on*gr_dp)''')
    # Reclaim report-string bytes for the exact navigator rewind. Arguments
    # and printed values are retained; only optional verbose labels shorten.
    for old, new in [
        ('\\nDW grad: X=%d, Y=%d, Z=%d DAC\\n', 'DW DAC %d %d %d\\n'),
        ('DW grad array for this b-value:\\n X=%ld, Y=%ld, Z=%ld,\\n', 'DW row %ld %ld %ld\\n'),
        ('\\nNominal diffusion b ~ %ld; excludes crusher\\n', 'Nominal b %ld; lobes only\\n'),
        ('\\nb report off (needs delta<=10ms, Delta<=80ms, unit dirs)\\n', 'b report unavailable\\n'),
    ]:
        s = once(s, '"'+old+'"', '"'+new+'"')
    # Offset frequency is present only in fixed RF windows. Buffer 6 restores
    # the centre frequency, retaining and explicitly accounting for phase.
    # Start-to-centre / start-to-end offset spans include the manual's reset
    # delivery time and the source mapper's 3-us RF latency (nominal model).
    old = '''\tfrequency_buffer(0);                    /*  buffer 0 = tx freq */
\tfrequency(MHz, kHz+kHz_new, Hz+Hz_new, rx1MHz);
\toffset_frequency(fov_slice_freq+slice_freq_var);
\treset_frequency();'''
    setup = '''    v1912_pos=(0L+fov_slice_off[pos_index])+(0L+slice_mm_10)*40L;
    if (v1912_pos!=0L)
    {
    starttimer();
    v1912_i=0;
v1912_freq_setup:
    v1912_q=v19_g_ex;
    if (v1912_i==2) v1912_q=v19_g_m;
    if (v1912_i==3) v1912_q=v19_g_re;
    v1912_q=v1912_q*grad_varl/32767L;
    v1912_q=-((v1912_pos/400L)*v1912_q+
        (v1912_pos%400L)*v1912_q/400L);
    if ((v1912_q<-32767L)||(v1912_q>32767L))
    { v19_error_code=149; goto v19_fail; }
    v1912_freq[v1912_i]=v1912_q;
    frequency_buffer(v1912_i);
    frequency(MHz,kHz,Hz,rx1MHz);
    offset_frequency(v1912_freq[v1912_i]);
    v1912_i=v1912_i+1;
    if (v1912_i==1) v1912_i=2;
    if (v1912_i<4) goto v1912_freq_setup;
    v1912_freq[1]=v1912_freq[0];
    frequency_buffer(6);
    frequency(MHz,kHz,Hz,rx1MHz);
    reset_frequency();
    waittimer(27000);
    starttimer();
    v1912_acc=0L;
    v1912_i=0;
v1912_phase_setup:
    v1912_j=v1912_i+18;
    if (v1912_i>=3) v1912_j=v1912_j+1;
    temp=v1912_i;
    if (temp==4) temp=3;
    v1912_q=v1912_acc+(0L+v1912_freq[temp])*
        ((0L+rf_length[v1912_j])*5L+(0L+v19_i_lead_m_anc)-414L);
    v1912_q=v1912_q%10000000L;
    if (v1912_q>=0L) v1912_q=v1912_q+3125L;
    else v1912_q=v1912_q-3125L;
    v1912_corr[v1912_i]=-(v1912_q/6250L);
    v1912_q=(0L+v1912_freq[temp])*
        ((0L+rf_length[v1912_j])*10L+(0L+v19_i_lead_m_anc)+225L);
    v1912_acc=(v1912_acc+v1912_q)%10000000L;
    v1912_i=v1912_i+1;
    if (v1912_i<5) goto v1912_phase_setup;
    v1912_span=(0L+v1912_freq[3])*((0L+rf_length[23])*10L+(0L+v19_i_lead_m_anc)+225L);
    v1912_centre=(0L+v1912_freq[3])*((0L+rf_length[23])*5L+(0L+v19_i_lead_m_anc)-414L);
    frequency_buffer(0);
    }
    else
    {
        frequency_buffer(0);
        frequency(MHz,kHz,Hz,rx1MHz);
        offset_frequency(fov_slice_freq);
        reset_frequency();
        v1912_i=0;
v1912_phase_zero:
        v1912_corr[v1912_i]=0;
        v1912_i=v1912_i+1;
        if (v1912_i<5) goto v1912_phase_zero;
    }'''
    s = once(s, old, setup)
    s = once(s, '#define V19_POST_RF 200L', '#define V19_POST_RF 800L')
    s = once(s, 'tr_min = v19_shot_us + 11350L + 70L + 69L + 5000L;',
             '''tr_min = v19_shot_us + 11350L + 70L + 69L + 5000L;
        if (v1912_pos!=0L) tr_min=tr_min+2700L;''')
    # Baseline zero-offset branch preserves its exact calls. The added work
    # is inside inherited waits and therefore cannot change RF/ADC centres.
    for idx, buf, corr in [(18, 0, 0), (19, 0, 1), (20, 2, 2), (22, 3, 3), (23, 3, 4)]:
        mul = {18: 'v19_mul_ex', 19: 'v19_mul_rf', 20: 'v19_mul_m',
               22: 'v19_mul_re', 23: 'v19_mul[v1912_flip]'}[idx]
        anchor = f'NEWSHAPE_SETUP({idx}, {mul})'
        inject = f'''\n    if (v1912_pos!=0L)
    {{
        waittimer(225);
        frequency_buffer({buf});
        reset_frequency();
    }}'''
        # Gate before unblank; retain the established warmup and RF deadlines.
        a = s.index(anchor)
        b = s.index('waittimer(v19_i_unblank);', a)
        s = s[:b] + inject + '\n' + s[b:]
        b = s.index('rfon(0);', b)
        tag = {18: 'ex', 19: 'rf', 20: 'm', 22: 're', 23: 'im'}[idx]
        b = s.index(f'waittimer(v19_i_offl_{tag}_p_post);', b)
        s = s[:b] + f'''
    if (v1912_pos!=0L)
    {{
        waittimer(v19_i_offl_{tag}_p_post-400);
        frequency_buffer(6);
        reset_frequency();
    }}
''' + s[b:]
    phases = [('phase(phase_90);', 'phase(phase_90+v1912_corr[0]);', 'v19_m_ex'),
              ('phase(phase_180);', 'phase(phase_180+v1912_corr[1]);', 'v19_m_rf'),
              ('phase(phase_90+2*deg_90);', 'phase(phase_90+2*deg_90+v1912_corr[2]);', 'v19_m_m'),
              ('phase(phase_90);', 'phase(phase_90+v1912_corr[3]);', 'v19_m_re'),
              ('phase(phase_180);', 'phase(phase_180+v1912_corr[4]);', 'v19_l_im')]
    start = s.index('v19_mat_window:')
    for old, new, landmark in phases:
        a = s.index(landmark, start)
        a = s.index(old, a)
        s = s[:a] + new + s[a+len(old):]
        start = a
    phase_update = '''    if ((v1912_pos!=0L)&&(echo_cnt>0))
    {
        v1912_q=v1912_acc+v1912_centre;
        v1912_q=v1912_q%10000000L;
        if (v1912_q>=0L) v1912_q=v1912_q+3125L;
        else v1912_q=v1912_q-3125L;
        v1912_corr[4]=-(v1912_q/6250L);
        v1912_acc=(v1912_acc+v1912_span)%10000000L;
        phase(phase_180+v1912_corr[4]);
    }
'''
    # Update before the next RF in the roomy lobe-to-RF wait, rather than in
    # the tight post-ADC or 8997-tick acquisition arithmetic window.
    s = once(s, '    waittimer(v19_i_go_im_m_lead);',
             phase_update+'    waittimer(v19_i_go_im_m_lead);')
    s = once(s, '    phase(phase_180+phase_correction);', '''    if (v1912_pos!=0L) phase(phase_180+v1912_corr[4]);
    else phase(phase_180+phase_correction);''')
    # After the readout return to the centre-frequency bank; the next RF gate
    # selects its own bank only at the fixed pulse-local target.
    s = once(s, '    frequency_buffer(0);\n    reset_frequency();',
             '    if (v1912_pos!=0L) frequency_buffer(6);\n    else frequency_buffer(0);\n    reset_frequency();')
    s = once(s, '\ttempl1 = slice_freq_long + IntToLong(slice_freq_var);',
             '''\ttempl1 = slice_freq_long + IntToLong(slice_freq_var);
    if (v1912_pos!=0L) templ1=0L;''')
    # Runtime no_views counts legacy ETL slots; embedded no_views is raw lines.
    s = '''/* V1912 raw contract: nav_on 0/1 retain inherited layout.
   nav_on 2: embedded no_views=R raw lines, views_per_seg=E+1 (shot
   length; console needs R % views_per_seg == 0); imaging ETL E.
   Imaging N=(R/(E+1)-1)*E; R must be divisible by E+1.
   Per volume and slice: leading E+1 unencoded volume navigator lines;
   then N/E imaging shots, each E imaging lines followed by one ky=0 echo.
   Physical raw views=R=(E+1)*(1+N/E), acquisition order unchanged across slices.
   Appended RF uses the final imaging flip; fused lobes and rewinders persist.
   Mode 2 mirrors the sampled P prephaser in its rewinder, cancelling its
   exact area. Mode 0/1 retain the inherited positive-ramp rounding residual.
   Off-centre TX offset is gated in fixed RF windows and accumulated phase is
   compensated at each RF centre. Nominal source spans: centre=RF/2+61.1 us,
   whole offset gate=RF+125 us. Reset frequency retains phase; it never clears
   the accumulated history. These spans use manual costs and 3-us RF latency;
   actual synthesizer/phase timing is a required phantom scanner check.
   Console slice position z maps to physical selector-axis position -z, the
   inherited positive bandwidth offset convention; angles remain locked.
   Generated from immutable v1.911 by examples/build_v1912_ppl.py. */
''' + s
    s = s.replace('V1911 ss-MGOT', 'V1912 ss-MGOT', 1)
    ppr = ppr.replace('FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppl',
                      'FSE_dwi_CPMG_non_CPMG_twoTE-1.912.ppl')
    return s, ppr


def main():
    s, ppr = build()
    OUT.write_text(s, encoding='latin-1', newline='\n')
    OUT.with_suffix('.ppr').write_text(ppr, encoding='latin-1', newline='\n')
    print(OUT)


if __name__ == '__main__':
    main()
