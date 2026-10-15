decimal
\ only forth also library definitions
\ lib-init
31     createlabels
\ PLATFORM: EVO
\ MR3031_PF1 FILE:c:\smis\seqlib\RFstd44.seq
\ MR3031_PF1 FILE:c:\smis\seqlib\gs_240Hz.seq
\ MR3031_PF1 FILE:c:\smis\seqlib\presat.seq
\ MR3031_PF1 FILE:c:\smis\seqlib\opt90_a.seq
\ MR3031_PF1 FILE:c:\smis\seqlib\opt90_as.seq
\ MR3031_PF1 FILE:c:\smis\seqlib\asym.seq
\ MR3031_PF1 FILE:c:\smis\seqlib\hypsec.seq
\ MR3031_PF1 FILE:c:\smis\seqlib\rfchess.seq
\ MR3031_PF1 FILE:c:\smis\seqlib\9lobsinb.seq
\ MR3031_PF1 FILE:c:\smis\seqlib\19lobsinb.seq
\ IMAGE SEQUENCE FILE:c:\smis\seqlib\g3040_15.seq
VARIABLE NO_ECHOES
VARIABLE CURRENT_ECHO
VARIABLE NO_SLICES
VARIABLE CURRENT_SLICE
VARIABLE SLICE_INTERLEAVE
VARIABLE BATCH_SLICES 0 BATCH_SLICES !
VARIABLE BATCH_INTERLEAVE 1 BATCH_INTERLEAVE !
VARIABLE NO_AVERAGES
VARIABLE IMAGE_AV
VARIABLE NO_VIEWS
VARIABLE CURRENT_VIEW
VARIABLE ECHO_CNT
VARIABLE SAMPLE_PERIOD
VARIABLE NO_SAMPLES
VARIABLE NO_DISCARD
VARIABLE VIEW_BLOCK
VARIABLE VIEW_AV
VARIABLE VIEWS_PER_SEG
VARIABLE SLICE_BLOCK
VARIABLE SLICE_AV
VARIABLE PHASE_CYCLE
VARIABLE NO_ACQ
\ COMMON OBS_MOD_LEVEL 0 f
VARIABLE TEMP_MAC
2VARIABLE TEMP_MAC_LONG
VARIABLE GROUP_DELAY
VARIABLE TRMIN
VARIABLE CLOCK
VARIABLE TFILTER 373 TFILTER !
VARIABLE TREF
VARIABLE TIME
VARIABLE TR_EXTEND
VARIABLE TE_MS
VARIABLE TE_US
VARIABLE TE_MS_2
VARIABLE TE_US_2
VARIABLE RET
\ COMMON TR 2 f
\ COMMON TE 4 f
\ COMMON TE_EFF 6 f
\ COMMON REPORT_ON 8 f
2VARIABLE TACQ
2VARIABLE TEMPL1
2VARIABLE TEMPL2
2VARIABLE TEMPL3
2VARIABLE TEMPL4
2VARIABLE TEMPL5
2VARIABLE TR_MIN
\ COMMON T_GS_COMP a f
\ COMMON TCRUSH c f
VARIABLE ASYMM
VARIABLE RF_SP_ANGLE
VARIABLE DEG_90
VARIABLE DEG_117
VARIABLE RFSP_ON
2VARIABLE RF_INC
2VARIABLE RF_SP_TEMP
VARIABLE DEG_360
VARIABLE OVERHEAD
2VARIABLE PHASE_ANG
VARIABLE REMAINDER_PHASE
VARIABLE PHASE_CORRECTION
VARIABLE PHASE_CORRECTION_0
VARIABLE PHASE_CORRECTION_1
VARIABLE PHASE_CORRECTION_2
\ COMMON RF_ON e f
\ COMMON SUBJ_ANGLE_X 10 f
\ COMMON SUBJ_ANGLE_Y 12 f
\ COMMON SUBJ_ANGLE_Z 14 f
\ COMMON RFCAL 16 f
\ COMMON MHZ 18 f
\ COMMON KHZ 1a f
\ COMMON HZ 1c f
\ COMMON RX1MHZ 1e f
\ COMMON REC_FREQ 20 f
VARIABLE PULSE_BWDTH
VARIABLE SLICE_OFFSET
VARIABLE SLICE_OFF_FREQ
VARIABLE KHZ_NEW
VARIABLE HZ_NEW
VARIABLE KHZ_NEW2
VARIABLE HZ_NEW2
VARIABLE KHZ_NEW3
VARIABLE HZ_NEW3
2VARIABLE SLICE_FREQ_LONG
2VARIABLE READ_FREQ_LONG
\ COMMON GATING 22 f
\ COMMON CARDIAC_DEL 24 f
VARIABLE FLOW_COMP_ON
VARIABLE PE_FLOW
VARIABLE PE_FLOW_SEC
VARIABLE GR_FLOW
VARIABLE GS_FLOW
VARIABLE FLOW_MAT
\ COMMON P_SAT_SCALE 26 f
\ COMMON SAT_TCRUSH 28 f
\ COMMON SAT_GR_AMP 2a f
VARIABLE RFNUM_SAT
VARIABLE TSEL_SAT
VARIABLE SAT_PULSE_BWDTH
VARIABLE FOV_SAT_SLICE_FREQ
VARIABLE SAT_CRUSH_AMP
VARIABLE SATGS_ON
VARIABLE SAT_LIST
VARIABLE SAT_CHANNEL
VARIABLE GS_SAT
VARIABLE SAT_MAT
VARIABLE SAT_MAT_2
VARIABLE SAT_ORIENT
VARIABLE SAT_FOV_SCALE
\ COMMON P_SAT_MUL 2c f
2VARIABLE SAT_SLICE_FREQ_LONG
VARIABLE PE_REPHASE_ON
VARIABLE GRAD_SPOIL_ON
VARIABLE GRAD_SPOIL_AMP
VARIABLE SLICE_REPHASE
\ COMMON GRAD_AMP 2e f
VARIABLE SLICE_LIST
VARIABLE READ_LIST
VARIABLE PHASE_LIST
VARIABLE SCALE_READ_OFF
VARIABLE SCALE_PHASE_OFF
VARIABLE SCALE_SLICE_OFF
VARIABLE FOV_READ_FREQ
VARIABLE FOV_PHASE_DEG
VARIABLE FOV_SLICE_FREQ
VARIABLE NEW_SLICE_OFFSET
VARIABLE GP_INC
VARIABLE GP_VAR
VARIABLE DACMAX 32767 DACMAX !
VARIABLE GP_INIT_VAR_RESCALE
VARIABLE GS_VAR_RESCALE
VARIABLE OVERSAMPLE
VARIABLE OVERSAMPLE2
VARIABLE GR_OVERSAMPLE
VARIABLE GR_UNDERSAMPLE
VARIABLE GP_OVERSAMPLE
VARIABLE GP_UNDERSAMPLE
4 CREATE-ARRAY GRAD_VAR
4 CREATE-ARRAY GRAD_VAR_L
VARIABLE TRAMP
VARIABLE GP_INIT_VAR
VARIABLE GR_VAR
VARIABLE GR_VAR_S
VARIABLE GS_VAR
VARIABLE GR_COMP
VARIABLE GR_COMP_S
VARIABLE GS_COMP
VARIABLE GS_COMP_S
VARIABLE GR_CRUSH
VARIABLE GS_CRUSH
VARIABLE GP_CRUSH
2VARIABLE DACMAXLONG 0x7fff 0x0 DACMAXLONG 2!
\ COMMON GR_COMP_SCALE 30 f
\ COMMON GS_COMP_SCALE 32 f
\ COMMON GR_ON 34 f
\ COMMON GP_ON 36 f
\ COMMON GS_ON 38 f
VARIABLE PHASE_90
VARIABLE PHASE_180
VARIABLE PHASE_117
VARIABLE TSEL90
VARIABLE TSEL180
\ COMMON P90_MUL 3a f
\ COMMON P180_MUL 3c f
VARIABLE WARMUP 20 WARMUP !
VARIABLE PHASE_RES 225 PHASE_RES !
VARIABLE RFNUM
VARIABLE PHASE_REC
VARIABLE PHASE_REC_CAL1
VARIABLE PHASE_REC_CAL2
40 CREATE-ARRAY RF_LENGTH
40 CREATE-ARRAY RF_BWDTH
40 CREATE-ARRAY RAD
40 CREATE-ARRAY RWT
40 CREATE-ARRAY RBD
\ COMMON P180_SCALE 3e f
\ COMMON ALPHA 40 f
VARIABLE POS_INDEX
512 CREATE-ARRAY FOV_READ_OFF
512 CREATE-ARRAY FOV_PHASE_OFF
512 CREATE-ARRAY FOV_SLICE_OFF
VARIABLE PHASE_VAR
512 CREATE-ARRAY S_ANGLE_VAR
512 CREATE-ARRAY P_ANGLE_VAR
512 CREATE-ARRAY R_ANGLE_VAR

VARIABLE MD_TDEL
VARIABLE MD_CLOCK
VARIABLE MD_ADDR
: MR3040_DELAY
MD_ADDR !
MD_CLOCK !
MD_TDEL !
MD_CLOCK @
   
10 noop
 >
IF
MD_TDEL @
10 noop
MD_CLOCK @
 */
MD_TDEL !
THEN
MD_TDEL @
   
 [ 56832 ,code 4095 ,code ]
 >
IF
BEGIN
0 noop
MD_ADDR @
1 noop
 [ 56832 ,code 4095 ,code ]
MR3040_OUTPUT
MD_TDEL @
   
 [ 56832 ,code 4095 ,code ]
 -
MD_TDEL !
MD_TDEL @
   
 [ 56832 ,code 4095 ,code ]
 > NOT
 UNTIL
THEN
0 noop
MD_ADDR @
1 noop
MD_TDEL @
MR3040_OUTPUT
 ;
VARIABLE TEMP_3040

VARIABLE CMT_MAT
VARIABLE CMT_S
VARIABLE CMT_P
VARIABLE CMT_R
VARIABLE CMT_I
: CREATEMATRIXTEST
CMT_R !
CMT_P !
CMT_S !
CMT_MAT !
CMT_MAT @
DACMAX @
CMT_S @
DACMAX @
CMT_P @
DACMAX @
CMT_R @
PHASE_VAR @
POS_INDEX @
2* S_ANGLE_VAR +
@
POS_INDEX @
2* P_ANGLE_VAR +
@
POS_INDEX @
2* R_ANGLE_VAR +
@
MR3040_CREATEMATRIX
CMT_I !
CMT_I @
IF
." Failed to create matrix = "
CMT_MAT @
 .
." , return code = "
CMT_I @
 .
 CR
THEN
CMT_I @
EXIT
 ;
VARIABLE GS_RP
VARIABLE GR_DP
VARIABLE GP_DP
VARIABLE GP_STORE
VARIABLE GP_VAR_CALC
VARIABLE GP_VAR_CALC_RESCALE
VARIABLE GP_CNT
VARIABLE GP_LOC
VARIABLE GP_MUL
VARIABLE VIEWS_PER_ECHO
VARIABLE ARRAY_COUNT
VARIABLE PHASE_COUNT
VARIABLE PHASE_OFFSET
VARIABLE SLICE_LIST_RP
VARIABLE READ_LIST_DP
VARIABLE PHASE_LIST_DP
VARIABLE GRP_DP
VARIABLE GSP_RP
\ COMMON FSE_GS_COMP 42 f
\ COMMON OVERHEAD_VAR 44 f
\ COMMON GRP_LOBE 46 f
\ COMMON GSP_LOBE 48 f
\ COMMON DE_PHASE 4a f
2VARIABLE TE_A
2VARIABLE TE_B
2VARIABLE SAMPLE_PERIOD_L
VARIABLE TE_EXTEND
VARIABLE TDP
VARIABLE TACQ_INT
VARIABLE DEL
2VARIABLE TACQ_2
2VARIABLE TE_BALANCE_AL
2VARIABLE TE_BALANCE_BL
2VARIABLE TE_BALANCE_BL_TEMP1
2VARIABLE TE_BALANCE_BL_TEMP2
2VARIABLE TE_BALANCE_BL_ESP
2VARIABLE TE_BALANCE_BL_TEMP1_ESP
\ COMMON POST_90_DELAY1 4c f
VARIABLE SLICE_180_REFOCUS
VARIABLE STIM_TCRUSH
VARIABLE TEMP
VARIABLE EXTRA_VAL
VARIABLE PE_ORDER
VARIABLE ECHO
VARIABLE SHOT
VARIABLE CNT
VARIABLE NAV_ON
VARIABLE NO_VIEWS_EFF
VARIABLE SETUP_MODE
\ COMMON TREF_SETUP 4e f
\ COMMON ESP 50 f
VARIABLE FOVF
VARIABLE VIEW_SHIFT
VARIABLE PF_ECHOES
2VARIABLE REC_SEL
VARIABLE GR_COMP_FLOW
VARIABLE GRP_DP_1
VARIABLE T_FLOW
VARIABLE G1
VARIABLE G2
2VARIABLE TR_EXTEND_US
2VARIABLE TR_EXTEND_USL
VARIABLE READ_PRE_LIST
VARIABLE SLICE_BATCH_START
6 CREATE-ARRAY PB_ON
6 CREATE-ARRAY PB_OFFSET
6 CREATE-ARRAY PB_FOV
6 CREATE-ARRAY PB_THK
0 CREATE-ARRAY PB_CHANNEL
 32 ,
 32 ,
 2 ,
 2 ,
 512 ,
 512 ,

6 CREATE-ARRAY PB_FREQ
6 CREATE-ARRAY PB_KHZ
6 CREATE-ARRAY PB_HZ
6 CREATE-ARRAY PB_GS_SAT
VARIABLE PB_INDEX
VARIABLE SAT_OFFSET
VARIABLE NO_PB
VARIABLE FOV_PHASE_OFF_SAT
VARIABLE FOV_READ_OFF_SAT
\ COMMON SAT_ON 52 f
\ COMMON INTER_PB_DELAY 54 f
\ COMMON P_SAT_MUL_1 56 f
\ COMMON PHCOR 58 f
\ COMMON PHCOR_PLUS 5a f
\ COMMON PHCOR_MINUS 5c f
\ COMMON R_PHCOR 5e f
0 CREATE-ARRAY SAT_ON_AR
 1 ,
 1 ,
 1 ,

VARIABLE GP_SL_INC
VARIABLE GP_SL_INIT_VAR
VARIABLE GP_SL_VAR
VARIABLE GP_SL_ON
VARIABLE NO_VIEWS_2
VARIABLE CURRENT_VIEW_2
VARIABLE FOV_SL_PHASE_OFF
VARIABLE FOV_SL_PHASE_DEG
VARIABLE OVERSAMPLE3
VARIABLE GP2_OVERSAMPLE
VARIABLE NAV_CNT
2VARIABLE GRAD_VARL
2VARIABLE BW_OVERRIDE
\ COMMON POST_CRUSH_ON 60 f
VARIABLE DE_ON
VARIABLE SLICE_180_CRUSH
VARIABLE SLICE_DE90_LIST
VARIABLE READ_DE90_LIST
VARIABLE POST_CRUSH_LIST
\ COMMON POST_TCRUSH 62 f
\ COMMON POST_CRUSH_AMP 64 f
VARIABLE NO_VIEWS_EFF_1
VARIABLE TOTAL_ECHO_CNT
VARIABLE DISCARD_CURRENT_ECHO
\ COMMON GATE_DURATION 66 f
\ COMMON GATE_INTERVAL 68 f
VARIABLE SAT_MODE
VARIABLE PB_GAP
\ COMMON PE2_CENTRIC_ON 6a f
\ COMMON ECHOES_TO_DISCARD 6c f
\ COMMON NO_SLICES_PER_GATING_INTERVAL 6e f
\ COMMON SLICE_CLUSTERING_ON 70 f
VARIABLE T_RESP_PLATEAU
VARIABLE NO_VIEWS_PER_GATING_INTERVAL
VARIABLE T_RESP_FRACTION
VARIABLE GATING_CONDITION
VARIABLE GATING_CONDITION_1
VARIABLE GATING_CONDITION_2
\ COMMON GATING_MODE 72 f
VARIABLE MAINS_GATING
VARIABLE POST_MAINS_GATE_DELAY
VARIABLE CHESS_LIST
\ COMMON TCRUSH_CHESS 74 f
\ COMMON T_CHESS 76 f
\ COMMON GS_CHESS_AMP 78 f
\ COMMON CHEM_SHIFT_FREQ 7a f
\ COMMON CHESS_ON 7c f
\ COMMON CHESS_GAUSS 7e f
\ COMMON CHESS_MUL 80 f
VARIABLE T_CHESS_GAUSS
VARIABLE CHESS_RFNUM
\ COMMON RFDELAY 82 f
\ COMMON RFGATE_DELAY 84 f
\ COMMON PHCOR0 86 f
\ COMMON SLICE_MM_10 88 f
2VARIABLE SLICE_FREQ_VAR
\ COMMON VALIDATE 8a f
\ COMMON NO_DISACQ 8c f
\ COMMON DISACQ_CNT 8e f
\ COMMON NOTDUMMY 90 f
VARIABLE SLAB_RATIO
5 CREATE-ARRAY GATING_TEMP1
5 CREATE-ARRAY GATING_TEMP2
VARIABLE GS_VAR1
\ COMMON HASPRINTED 92 f
\ COMMON INTERSLICE_DELAY 94 f
\ COMMON PHASE_SIGN 96 f
\ COMMON USE_PDD 98 f
\ COMMON PDD_TX_MASK 9a f
\ COMMON PDD_RX_MASK 9c f
\ COMMON PTS_MASK 9e f
VARIABLE MTC_LIST
\ COMMON MTC_ON a0 f
\ COMMON NO_CEST_PULSES a2 f
\ COMMON INTER_CEST_DELAY a4 f
\ COMMON POST_CEST_DELAY a6 f
VARIABLE CEST_COUNT
VARIABLE INTER_CEST_CAL
VARIABLE INTER_CEST_CAL_MIN
VARIABLE MTC_RFNUM
VARIABLE MTC_GAUSSIAN
VARIABLE MTC_FREQ_MAX
VARIABLE MTC_FREQ_STEP
2VARIABLE TSELMTCL
\ COMMON MTC_AMP1 a8 f
\ COMMON TSELMTC_MS aa f
\ COMMON MTC_TCRUSH ac f
\ COMMON MTC_GR_AMP ae f
\ COMMON MTC_FREQ b0 f
\ COMMON MTC_MUL b2 f
VARIABLE NO_EXPERIMENTS
VARIABLE COMPLETED_EX
VARIABLE MTC_ARRAY_ON
1000 CREATE-ARRAY MTC_FREQ_ARRAY
VARIABLE OTHER_CHANNEL
VARIABLE GATING_AFTER_TR_ON
2VARIABLE RF_EXTEND_DELAY
VARIABLE DIXON_ON
VARIABLE DELTA_2
VARIABLE DELTA_2_90
VARIABLE DELTA_0
VARIABLE SMODE
64 CREATE-ARRAY TR_ARRAY
VARIABLE TR_ARRAY_SIZE
2VARIABLE POST_90_DELAY0L
2VARIABLE PRE_90_DELAY0L
VARIABLE BAD_CNT
VARIABLE B_MAX
VARIABLE NO_B_STEPS
VARIABLE B_INC
VARIABLE MAX_DIFF_GRAD
VARIABLE MAX_DIFF_GRAD_PC
VARIABLE DIFF_GRAD
VARIABLE B_STEP_CNT
VARIABLE DIFF_LIST
VARIABLE DIFF_LIST2
VARIABLE DIFF_DIR_CNT
VARIABLE DIFF_SLICE
VARIABLE DIFF_READ
VARIABLE DIFF_PHASE
VARIABLE DIFF_TRAMP
VARIABLE DIFF_CLOCK
2VARIABLE B_DIFF_SLICE
2VARIABLE B_DIFF_READ
2VARIABLE B_DIFF_PHASE
2VARIABLE GMAX
VARIABLE SM_DELTA
VARIABLE BIG_DELTA
2VARIABLE BIG_DELTA_MIN
2VARIABLE BIG_DELTA_MAX_4_GIVEN_TE
VARIABLE DIFF_COMP
VARIABLE EXPT
2VARIABLE BIG_DELTA_US
2VARIABLE SM_DELTA_US
\ COMMON DIFF_ON b4 f
\ COMMON DIFF_NON_ZERO b6 f
16 CREATE-ARRAY B_GRADS_ARRAY
16 CREATE-ARRAY B_STEPS_ARRAY
48 CREATE-ARRAY DIFF_GRAD_DIR
\ COMMON DIFF_TCRUSH b8 f
\ COMMON TCRUSH1 ba f
\ COMMON DIFF_GRAD_SCALE bc f
2VARIABLE SPACE_PRE
2VARIABLE SPACE_POST
2VARIABLE EXTRA_TE
2VARIABLE EXTRA_TE2
2VARIABLE EXTRA_DELTA
2VARIABLE EXTRA_TE_US
2VARIABLE EXTRA_TE2_US
2VARIABLE EXTRA_DELTA_US
2VARIABLE EXTRA_DELTA2_US
VARIABLE NO_DIFF_DIR
2VARIABLE MIN_PRE
2VARIABLE MIN_POST
2VARIABLE TRUE_HALF_TE_US
2VARIABLE TE_US_LONG
2VARIABLE MIN_TE
2VARIABLE T_SEGMENT
2VARIABLE T_PROFILE
: MAIN STREAMON DECIMAL
NO_AVERAGES @
   
VIEW_BLOCK @
 /
   
VIEW_BLOCK @
 [ 45207 ,code 48662 ,code ] swapdrop
   
NO_AVERAGES @
 !=
IF
 CR
." No. Averages not a multiple of View Block"
                                      XGOTO 0
THEN
VIEW_BLOCK @
   
SLICE_BLOCK @
 /
   
SLICE_BLOCK @
 [ 45207 ,code 48662 ,code ] swapdrop
   
VIEW_BLOCK @
 !=
IF
 CR
." View Block not a multiple of Slice Block"
                                      XGOTO 0
THEN
PHASE_CYCLE @
   
2 noop
 =
IF
NO_AVERAGES @
   
1 noop
 AND
   
0 noop
 !=
IF
 CR
." No. Averages is not a multiple of 2"
                                      XGOTO 0
THEN
THEN
[ 56832 ,code 152 ,code ] 15 far@
   
0 noop
 >
IF
[ 56832 ,code 156 ,code ] 15 far@
USEROUT
THEN
1 noop
[ 56832 ,code 150 ,code ] 15 far!
TRAMP @
   
 [ 56832 ,code 40 ,code ]
 -
   
[ 56832 ,code 130 ,code ] 15 far@
 +
   
[ 56832 ,code 132 ,code ] 15 far@
   
17 noop
 -
 -
   
10 noop
 <
IF
." Illegal parameter"
 CR
                                      XGOTO 0
THEN
0 noop
[ 56832 ,code 68 ,code ] 15 far!
0 noop
[ 56832 ,code 66 ,code ] 15 far!
0 noop
2* GRAD_VAR +
@
   
0 noop
 <
IF
 [ 56832 ,code 0 ,code 56832 ,code 1 ,code  ]
   
0 noop
2* GRAD_VAR +
@
S>D
 D+
GRAD_VARL 2!
 ELSE
0 noop
2* GRAD_VAR +
@
S>D
GRAD_VARL 2!
THEN
0 noop
DIFF_COMP !
BIG_DELTA @
INTTOLONG
BIG_DELTA_US 2!
SM_DELTA @
INTTOLONG
SM_DELTA_US 2!
 [ 56832 ,code 6688 ,code ]
1 noop
2* RAD +
!
20 noop
1 noop
2* RWT +
!
 [ 56832 ,code -240 ,code ]
1 noop
2* RBD +
!
 [ 56832 ,code 1332 ,code ]
1 noop
2* RF_LENGTH +
!
 [ 56832 ,code 3000 ,code ]
1 noop
2* RF_BWDTH +
!
 [ 56832 ,code 5352 ,code ]
2 noop
2* RAD +
!
 [ 56832 ,code 40 ,code ]
2 noop
2* RWT +
!
 [ 56832 ,code -240 ,code ]
2 noop
2* RBD +
!
 [ 56832 ,code 2664 ,code ]
2 noop
2* RF_LENGTH +
!
 [ 56832 ,code 1500 ,code ]
2 noop
2* RF_BWDTH +
!
 [ 56832 ,code 4016 ,code ]
3 noop
2* RAD +
!
 [ 56832 ,code 80 ,code ]
3 noop
2* RWT +
!
 [ 56832 ,code -240 ,code ]
3 noop
2* RBD +
!
 [ 56832 ,code 5328 ,code ]
3 noop
2* RF_LENGTH +
!
 [ 56832 ,code 750 ,code ]
3 noop
2* RF_BWDTH +
!
 [ 56832 ,code 8024 ,code ]
4 noop
2* RAD +
!
20 noop
4 noop
2* RWT +
!
 [ 56832 ,code -240 ,code ]
4 noop
2* RBD +
!
 [ 56832 ,code 2000 ,code ]
4 noop
2* RF_LENGTH +
!
 [ 56832 ,code 3000 ,code ]
4 noop
2* RF_BWDTH +
!
 [ 56832 ,code 2016 ,code ]
5 noop
2* RAD +
!
 [ 56832 ,code 40 ,code ]
5 noop
2* RWT +
!
 [ 56832 ,code -240 ,code ]
5 noop
2* RBD +
!
 [ 56832 ,code 4000 ,code ]
5 noop
2* RF_LENGTH +
!
 [ 56832 ,code 1500 ,code ]
5 noop
2* RF_BWDTH +
!
16 noop
6 noop
2* RAD +
!
 [ 56832 ,code 80 ,code ]
6 noop
2* RWT +
!
 [ 56832 ,code -240 ,code ]
6 noop
2* RBD +
!
 [ 56832 ,code 8000 ,code ]
6 noop
2* RF_LENGTH +
!
 [ 56832 ,code 750 ,code ]
6 noop
2* RF_BWDTH +
!
 [ 56832 ,code 11024 ,code ]
7 noop
2* RAD +
!
20 noop
7 noop
2* RWT +
!
 [ 56832 ,code -240 ,code ]
7 noop
2* RBD +
!
 [ 56832 ,code 666 ,code ]
7 noop
2* RF_LENGTH +
!
 [ 56832 ,code 6000 ,code ]
7 noop
2* RF_BWDTH +
!
 [ 56832 ,code 11688 ,code ]
8 noop
2* RAD +
!
20 noop
8 noop
2* RWT +
!
 [ 56832 ,code -240 ,code ]
8 noop
2* RBD +
!
 [ 56832 ,code 1000 ,code ]
8 noop
2* RF_LENGTH +
!
 [ 56832 ,code 4000 ,code ]
8 noop
2* RF_BWDTH +
!
 [ 56832 ,code -31608 ,code ]
9 noop
2* RAD +
!
 [ 56832 ,code 200 ,code ]
9 noop
2* RWT +
!
 [ 56832 ,code -240 ,code ]
9 noop
2* RBD +
!
 [ 56832 ,code 10000 ,code ]
9 noop
2* RF_LENGTH +
!
 [ 56832 ,code 1500 ,code ]
9 noop
2* RF_BWDTH +
!
 [ 56832 ,code -30608 ,code ]
10 noop
2* RAD +
!
 [ 56832 ,code 160 ,code ]
10 noop
2* RWT +
!
 [ 56832 ,code -240 ,code ]
10 noop
2* RBD +
!
 [ 56832 ,code 8000 ,code ]
10 noop
2* RF_LENGTH +
!
 [ 56832 ,code 1875 ,code ]
10 noop
2* RF_BWDTH +
!
 [ 56832 ,code -29608 ,code ]
11 noop
2* RAD +
!
 [ 56832 ,code 100 ,code ]
11 noop
2* RWT +
!
 [ 56832 ,code -240 ,code ]
11 noop
2* RBD +
!
 [ 56832 ,code 5000 ,code ]
11 noop
2* RF_LENGTH +
!
 [ 56832 ,code 3000 ,code ]
11 noop
2* RF_BWDTH +
!
 [ 56832 ,code -28608 ,code ]
12 noop
2* RAD +
!
 [ 56832 ,code 80 ,code ]
12 noop
2* RWT +
!
 [ 56832 ,code -240 ,code ]
12 noop
2* RBD +
!
 [ 56832 ,code 4000 ,code ]
12 noop
2* RF_LENGTH +
!
 [ 56832 ,code 3750 ,code ]
12 noop
2* RF_BWDTH +
!
 [ 56832 ,code -27608 ,code ]
13 noop
2* RAD +
!
 [ 56832 ,code 40 ,code ]
13 noop
2* RWT +
!
 [ 56832 ,code -240 ,code ]
13 noop
2* RBD +
!
 [ 56832 ,code 2000 ,code ]
13 noop
2* RF_LENGTH +
!
 [ 56832 ,code 7500 ,code ]
13 noop
2* RF_BWDTH +
!
 [ 56832 ,code -26608 ,code ]
14 noop
2* RAD +
!
 [ 56832 ,code 200 ,code ]
14 noop
2* RWT +
!
 [ 56832 ,code -240 ,code ]
14 noop
2* RBD +
!
 [ 56832 ,code 7000 ,code ]
14 noop
2* RF_LENGTH +
!
 [ 56832 ,code 180 ,code ]
14 noop
2* RF_BWDTH +
!
 [ 56832 ,code -24608 ,code ]
15 noop
2* RAD +
!
20 noop
15 noop
2* RWT +
!
 [ 56832 ,code -240 ,code ]
15 noop
2* RBD +
!
 [ 56832 ,code 2000 ,code ]
15 noop
2* RF_LENGTH +
!
 [ 56832 ,code 5000 ,code ]
15 noop
2* RF_BWDTH +
!
 [ 56832 ,code -22608 ,code ]
16 noop
2* RAD +
!
20 noop
16 noop
2* RWT +
!
 [ 56832 ,code -240 ,code ]
16 noop
2* RBD +
!
 [ 56832 ,code 2000 ,code ]
16 noop
2* RF_LENGTH +
!
 [ 56832 ,code 10000 ,code ]
16 noop
2* RF_BWDTH +
!
 [ 56832 ,code -26608 ,code ]
17 noop
2* RAD +
!
 [ 56832 ,code 200 ,code ]
17 noop
2* RWT +
!
 [ 56832 ,code -240 ,code ]
17 noop
2* RBD +
!
 [ 56832 ,code 20000 ,code ]
17 noop
2* RF_LENGTH +
!
10 noop
17 noop
2* RF_BWDTH +
!
SAMPLE_PERIOD @
ACQPAD
GROUP_DELAY !
SAMPLE_PERIOD @
   
19 noop
 >
IF
 [ 56832 ,code 51 ,code ]
EXTRA_VAL !
THEN
SAMPLE_PERIOD @
   
20 noop
 =
IF
3 noop
EXTRA_VAL !
THEN
SAMPLE_PERIOD @
   
15 noop
 =
IF
3 noop
EXTRA_VAL !
THEN
SAMPLE_PERIOD @
   
10 noop
 =
IF
 [ 56832 ,code 38 ,code ]
EXTRA_VAL !
THEN
SAMPLE_PERIOD @
   
5 noop
 =
IF
 [ 56832 ,code 59 ,code ]
EXTRA_VAL !
THEN
GROUP_DELAY @
   
16 noop
 +
   
EXTRA_VAL @
 +
S>D
TEMPL1 2!
TEMPL1 q2@
   
 [ 56832 ,code 16 ,code 56832 ,code 0 ,code  ]
 D*
TEMPL1 2!
TEMPL1 q2@
   
 [ 56832 ,code 100 ,code 56832 ,code 0 ,code  ]
 D/
TEMPL1 2!
TEMPL1 q2@
DROP
OVERHEAD !
SAMPLE_PERIOD @
ACQPAD
   
10 noop
 /
TFILTER !
PHASE_VAR @
   
1 noop
 =
IF
2 noop
0 noop
2* PB_CHANNEL +
!
2 noop
1 noop
2* PB_CHANNEL +
!
 [ 56832 ,code 32 ,code ]
2 noop
2* PB_CHANNEL +
!
 [ 56832 ,code 32 ,code ]
3 noop
2* PB_CHANNEL +
!
THEN
TRAMP @
   
3 noop
 [ 45207 ,code 48662 ,code ] swapdrop
   
[ 56832 ,code 78 ,code ] 15 far@
 +
   
[ 56832 ,code 130 ,code ] 15 far@
 -
   
 [ 56832 ,code 43 ,code ]
 <
IF
." Illegal parameter (2)"
 CR
                                      XGOTO 0
THEN
TRAMP @
   
3 noop
 [ 45207 ,code 48662 ,code ] swapdrop
   
[ 56832 ,code 78 ,code ] 15 far@
 +
   
TFILTER @
 -
   
[ 56832 ,code 130 ,code ] 15 far@
 -
   
 [ 56832 ,code 500 ,code ]
 +
   
 [ 56832 ,code 69 ,code ]
 <
IF
." Illegal parameter (3)"
 CR
                                      XGOTO 0
THEN
NO_EXPERIMENTS @
   
NO_B_STEPS @
   
NO_DIFF_DIR @
 [ 45207 ,code 48662 ,code ] swapdrop
 n/rem
   
0 noop
 !=
IF
." No expts should be divisible by no of b-steps ("
NO_B_STEPS @
 .
." ) * no directions ("
NO_DIFF_DIR @
 .
." )"
 CR
                                      XGOTO 0
THEN
NO_EXPERIMENTS @
   
NO_B_STEPS @
 <
IF
." Number of expts must be = no_b_steps"
 CR
." Set the Experiment Array Size to "
NO_B_STEPS @
 .
."  "
 CR
                                      XGOTO 0
THEN
NAV_ON @
   
1 noop
 =
   
NO_VIEWS @
   
VIEWS_PER_SEG @
 +
   
 [ 56832 ,code 1024 ,code ]
 >
 &&
IF
." No views + navgiators should be less than "
 [ 56832 ,code 1024 ,code ]
 .
 CR
                                      XGOTO 0
THEN
[ 56832 ,code 180 ,code ] 15 far@
   
0 noop
 =
IF
[ 56832 ,code 80 ,code ] 15 far@
   
0 noop
 =
IF
." Base TE (esp) be a multiple of eff. echo time (TE) when Diffusion is OFF "
 CR
                                      XGOTO 0
THEN
[ 56832 ,code 4 ,code ] 15 far@
1 noop
[ 56832 ,code 80 ,code ] 15 far@
 */
[ 56832 ,code 6 ,code ] 15 far!
 ELSE
1 noop
[ 56832 ,code 6 ,code ] 15 far!
PE_ORDER @
   
1 noop
 !=
IF
PE_ORDER @
   
5 noop
 !=
IF
." Set PE order to 1 or 5 for DWI"
 CR
                                      XGOTO 0
THEN
THEN
THEN
PE_ORDER @
   
2 noop
 !=
IF
NO_VIEWS @
NO_VIEWS_EFF !
NAV_ON @
   
1 noop
 =
IF
NO_VIEWS @
   
VIEWS_PER_SEG @
 -
NO_VIEWS_EFF !
THEN
NO_VIEWS_EFF @
   
2 noop
 n/rem
   
0 noop
 !=
   
PE_ORDER @
   
5 noop
 !=
 &&
IF
." Effective number of views must be even number"
 CR
                                      XGOTO 0
THEN
PF_ECHOES @
   
0 noop
 =
IF
VIEWS_PER_SEG @
PF_ECHOES !
THEN
PF_ECHOES @
   
VIEWS_PER_SEG @
 <
IF
." PF eff echoes must be >= VPS"
 CR
                                      XGOTO 0
THEN
PF_ECHOES @
   
2 noop
   
VIEWS_PER_SEG @
 [ 45207 ,code 48662 ,code ] swapdrop
 < NOT
IF
." PF eff echoes must be < 2*VPS"
 CR
                                      XGOTO 0
THEN
NO_VIEWS_EFF @
   
2 noop
   
VIEWS_PER_SEG @
 [ 45207 ,code 48662 ,code ] swapdrop
 /
VIEWS_PER_ECHO !
PF_ECHOES @
   
VIEWS_PER_SEG @
 -
   
VIEWS_PER_ECHO @
 [ 45207 ,code 48662 ,code ] swapdrop
VIEW_SHIFT !
 ELSE
NO_VIEWS @
   
[ 56832 ,code 6 ,code ] 15 far@
 -
   
1 noop
 +
   
2 noop
 [ 45207 ,code 48662 ,code ] swapdrop
NO_VIEWS_EFF !
NO_VIEWS @
   
[ 56832 ,code 6 ,code ] 15 far@
 > NOT
IF
." no_views must be > te_eff"
 CR
                                      XGOTO 0
THEN
0 noop
VIEW_SHIFT !
THEN
[ 56832 ,code 6 ,code ] 15 far@
   
[ 56832 ,code 108 ,code ] 15 far@
 -
[ 56832 ,code 6 ,code ] 15 far!
[ 56832 ,code 8 ,code ] 15 far@
IF
." First "
[ 56832 ,code 108 ,code ] 15 far@
 .
."  echoes discarded: "
THEN
[ 56832 ,code 6 ,code ] 15 far@
   
0 noop
 <
IF
." te_eff must be >0"
 CR
                                      XGOTO 0
 ELSE
[ 56832 ,code 8 ,code ] 15 far@
IF
." te_eff="
[ 56832 ,code 6 ,code ] 15 far@
 .
 CR
THEN
THEN
[ 56832 ,code 6 ,code ] 15 far@
   
VIEWS_PER_SEG @
 >
IF
." The eff echo time is too large"
 CR
                                      XGOTO 0
THEN
0 noop
CNT !
NAV_ON @
IF
LABEL 1
CNT @
   
VIEWS_PER_SEG @
 <
IF
0 noop
 [ 56832 ,code 1024 ,code ]
   
CNT @
 +
5 noop
PW
CNT @
   
1 noop
 +
CNT !
XGOTO 1
THEN
THEN
VIEWS_PER_SEG @
   
1 noop
 =
IF
PE_ORDER @
   
5 noop
 !=
IF
." Set PE order to 5 for single echo"
 CR
                                      XGOTO 0
THEN
THEN
PE_ORDER @
   
5 noop
 =
IF
VIEWS_PER_SEG @
   
1 noop
 !=
IF
." Set Echo train to 1 for single echo"
 CR
                                      XGOTO 0
THEN
THEN
PE_ORDER @
   
2 noop
 <
IF
NO_VIEWS_EFF @
   
VIEWS_PER_SEG @
   
2 noop
 [ 45207 ,code 48662 ,code ] swapdrop
 n/rem
   
0 noop
 !=
IF
." Number of views / (2*views per segment) must be an integer "
 CR
                                      XGOTO 0
THEN
THEN
PE_ORDER @
   
0 noop
 =
IF
                                      XGOTO 2
THEN
PE_ORDER @
   
1 noop
 =
IF
                                      XGOTO 3
THEN
PE_ORDER @
   
2 noop
 =
IF
                                      XGOTO 4
THEN
PE_ORDER @
   
5 noop
 =
IF
                                      XGOTO 5
THEN
LABEL 2
PE_ORDER @
   
0 noop
 =
   
VIEWS_PER_SEG @
   
4 noop
 <
 &&
IF
." Minimum echo train length is 4 for selected PE order"
 CR
                                      XGOTO 0
THEN
0 noop
ARRAY_COUNT !
LABEL 6
ARRAY_COUNT @
   
1 noop
 +
ARRAY_COUNT !
ARRAY_COUNT @
   
[ 56832 ,code 6 ,code ] 15 far@
 -
   
VIEWS_PER_ECHO @
 [ 45207 ,code 48662 ,code ] swapdrop
   
1 noop
 -
GP_MUL !
GP_MUL @
   
NO_VIEWS_EFF @
 0-
   
2 noop
 /
   
VIEW_SHIFT @
 -
 <
IF
GP_MUL @
   
NO_VIEWS_EFF @
 +
GP_MUL !
THEN
GP_MUL @
   
NO_VIEWS_EFF @
   
2 noop
 /
   
VIEW_SHIFT @
 -
 < NOT
IF
GP_MUL @
   
NO_VIEWS_EFF @
 -
GP_MUL !
THEN
GP_MUL @
0 noop
   
ARRAY_COUNT @
 +
5 noop
PW
1 noop
   
[ 56832 ,code 6 ,code ] 15 far@
 -
   
ARRAY_COUNT @
 -
   
VIEWS_PER_ECHO @
 [ 45207 ,code 48662 ,code ] swapdrop
   
1 noop
 -
GP_MUL !
GP_MUL @
   
NO_VIEWS_EFF @
 0-
   
2 noop
 /
   
VIEW_SHIFT @
 -
 <
IF
GP_MUL @
   
NO_VIEWS_EFF @
 +
GP_MUL !
THEN
GP_MUL @
   
NO_VIEWS_EFF @
   
2 noop
 /
   
VIEW_SHIFT @
 -
 < NOT
IF
GP_MUL @
   
NO_VIEWS_EFF @
 -
GP_MUL !
THEN
GP_MUL @
0 noop
   
ARRAY_COUNT @
 +
   
VIEWS_PER_SEG @
 +
5 noop
PW
ARRAY_COUNT @
   
VIEWS_PER_SEG @
 <
IF
XGOTO 6
THEN
0 noop
ARRAY_COUNT !
LABEL 7
ARRAY_COUNT @
   
1 noop
 +
ARRAY_COUNT !
VIEWS_PER_ECHO @
   
2 noop
 /
   
ARRAY_COUNT @
 -
   
1 noop
 +
TEMP !
TEMP @
 [ 56832 ,code 512 ,code ]
   
ARRAY_COUNT @
 +
5 noop
PW
TEMP @
 [ 56832 ,code 512 ,code ]
   
ARRAY_COUNT @
 +
   
VIEWS_PER_ECHO @
 +
5 noop
PW
ARRAY_COUNT @
   
VIEWS_PER_ECHO @
 <
IF
XGOTO 7
THEN
CNT @
ARRAY_COUNT !
0 noop
GP_LOC !
0 noop
GP_STORE !
LABEL 8
GP_LOC @
   
1 noop
 +
GP_LOC !
GP_LOC @
   
VIEWS_PER_ECHO @
 >
IF
VIEWS_PER_SEG @
GP_STORE !
THEN
0 noop
GP_CNT !
LABEL 9
GP_CNT @
   
1 noop
 +
GP_CNT !
0 noop
   
GP_CNT @
 +
   
GP_STORE @
 +
5 noop
PR
   
 [ 56832 ,code 512 ,code ]
   
GP_LOC @
 +
5 noop
PR
 +
GP_MUL !
GP_MUL @
   
NO_VIEWS_EFF @
 0-
   
2 noop
 /
   
VIEW_SHIFT @
 -
 <
IF
GP_MUL @
   
NO_VIEWS_EFF @
 +
GP_MUL !
THEN
GP_MUL @
   
NO_VIEWS_EFF @
   
2 noop
 /
   
VIEW_SHIFT @
 -
 < NOT
IF
GP_MUL @
   
NO_VIEWS_EFF @
 -
GP_MUL !
THEN
GP_MUL @
 [ 56832 ,code 1024 ,code ]
   
ARRAY_COUNT @
 +
5 noop
PW
ARRAY_COUNT @
   
1 noop
 +
ARRAY_COUNT !
GP_CNT @
   
VIEWS_PER_SEG @
 <
IF
XGOTO 9
THEN
GP_LOC @
   
2 noop
   
VIEWS_PER_ECHO @
 [ 45207 ,code 48662 ,code ] swapdrop
 <
IF
XGOTO 8
THEN
                                      XGOTO 10
LABEL 3
1 noop
SHOT !
NO_VIEWS_EFF @
NO_VIEWS_EFF_1 !
NO_VIEWS_EFF_1 @
   
2 noop
 /
   
VIEWS_PER_ECHO @
 -
   
1 noop
 -
GP_LOC !
LABEL 11
1 noop
ECHO !
GP_LOC @
   
1 noop
 +
GP_LOC !
LABEL 12
SHOT @
   
VIEWS_PER_ECHO @
 >
IF
GP_LOC @
   
VIEWS_PER_ECHO @
   
ECHO @
   
[ 56832 ,code 6 ,code ] 15 far@
 -
 [ 45207 ,code 48662 ,code ] swapdrop
 +
GP_MUL !
 ELSE
GP_LOC @
   
VIEWS_PER_ECHO @
   
ECHO @
   
[ 56832 ,code 6 ,code ] 15 far@
 -
 [ 45207 ,code 48662 ,code ] swapdrop
 -
GP_MUL !
THEN
GP_MUL @
   
NO_VIEWS_EFF_1 @
   
2 noop
 /
 -
 [ 56832 ,code 1024 ,code ]
   
CNT @
 +
5 noop
PW
CNT @
   
1 noop
 +
CNT !
ECHO @
   
1 noop
 +
ECHO !
ECHO @
   
VIEWS_PER_SEG @
   
1 noop
 +
 <
IF
XGOTO 12
THEN
SHOT @
   
1 noop
 +
SHOT !
SHOT @
   
VIEWS_PER_ECHO @
   
2 noop
 [ 45207 ,code 48662 ,code ] swapdrop
   
1 noop
 +
 <
IF
XGOTO 11
THEN
                                      XGOTO 10
LABEL 4
NAV_ON @
   
1 noop
 =
IF
." Navigators are not supported with selected PE order"
 CR
                                      XGOTO 0
THEN
1 noop
VIEWS_PER_ECHO !
CNT @
ARRAY_COUNT !
[ 56832 ,code 6 ,code ] 15 far@
 0-
   
1 noop
 +
TEMP !
VIEWS_PER_SEG @
   
NO_VIEWS @
 !=
IF
." Views per segment (ETL) must be equal number of Views for this PE order"
 CR
                                      XGOTO 0
THEN
0 noop
 [ 56832 ,code 1024 ,code ]
5 noop
PW
1 noop
 [ 56832 ,code 1025 ,code ]
5 noop
PW
2 noop
ARRAY_COUNT !
BEGIN
 [ 56832 ,code -1 ,code ]
RET !
ARRAY_COUNT @
   
2 noop
 n/rem
   
1 noop
 =
IF
1 noop
RET !
THEN
RET @
   
ARRAY_COUNT @
   
1 noop
 +
 [ 45207 ,code 48662 ,code ] swapdrop
   
2 noop
 /
 [ 56832 ,code 1024 ,code ]
   
ARRAY_COUNT @
 +
5 noop
PW
ARRAY_COUNT @
   
1 noop
 +
ARRAY_COUNT !
ARRAY_COUNT @
   
NO_VIEWS @
 =
 UNTIL
                                      XGOTO 10
LABEL 5
NAV_ON @
   
1 noop
 =
IF
." Navigators are not supported with selected PE order"
 CR
                                      XGOTO 0
THEN
[ 56832 ,code 8 ,code ] 15 far@
IF
." Kernel offset (for reconstruction)="
[ 56832 ,code 6 ,code ] 15 far@
 .
 CR
THEN
1 noop
VIEWS_PER_ECHO !
CNT @
ARRAY_COUNT !
[ 56832 ,code 6 ,code ] 15 far@
 0-
   
1 noop
 +
TEMP !
VIEWS_PER_SEG @
   
1 noop
 =
IF
NO_VIEWS @
 0-
   
2 noop
 /
TEMP !
THEN
BEGIN
TEMP @
 [ 56832 ,code 1024 ,code ]
   
ARRAY_COUNT @
 +
5 noop
PW
TEMP @
   
1 noop
 +
TEMP !
ARRAY_COUNT @
   
1 noop
 +
ARRAY_COUNT !
ARRAY_COUNT @
   
NO_VIEWS @
 =
 UNTIL
                                      XGOTO 10
LABEL 10
NO_VIEWS_2 @
 0-
   
2 noop
 /
TEMP !
0 noop
GP_CNT !
[ 56832 ,code 106 ,code ] 15 far@
   
0 noop
 =
IF
BEGIN
TEMP @
 [ 56832 ,code 2048 ,code ]
   
GP_CNT @
 +
5 noop
PW
TEMP @
   
1 noop
 +
TEMP !
GP_CNT @
   
1 noop
 +
GP_CNT !
GP_CNT @
   
NO_VIEWS_2 @
 =
 UNTIL
 ELSE
NO_VIEWS_2 @
   
2 noop
 >
IF
0 noop
 [ 56832 ,code 2048 ,code ]
5 noop
PW
 [ 56832 ,code -1 ,code ]
 [ 56832 ,code 2049 ,code ]
5 noop
PW
2 noop
GP_CNT !
BEGIN
1 noop
RET !
GP_CNT @
   
2 noop
 n/rem
   
1 noop
 =
IF
 [ 56832 ,code -1 ,code ]
RET !
THEN
RET @
   
GP_CNT @
   
1 noop
 +
 [ 45207 ,code 48662 ,code ] swapdrop
   
2 noop
 /
 [ 56832 ,code 2048 ,code ]
   
GP_CNT @
 +
5 noop
PW
GP_CNT @
   
1 noop
 +
GP_CNT !
GP_CNT @
   
NO_VIEWS_2 @
 =
 UNTIL
 ELSE
0 noop
 [ 56832 ,code 2048 ,code ]
5 noop
PW
 [ 56832 ,code -1 ,code ]
 [ 56832 ,code 2049 ,code ]
5 noop
PW
THEN
THEN
LABEL 13
NO_DISCARD @
DISCARD
1 noop
PHASE_INCREMENT
 [ 56832 ,code 90 ,code ]
 [ 56832 ,code 1000 ,code ]
PHASE_RES @
 */
DEG_90 !
 [ 56832 ,code 360 ,code ]
 [ 56832 ,code 1000 ,code ]
PHASE_RES @
 */
DEG_360 !
SAMPLE_PERIOD @
S>D
SAMPLE_PERIOD_L 2!
SAMPLE_PERIOD_L q2@
   
NO_SAMPLES @
   
NO_DISCARD @
 +
S>D
 D*
   
10 noop
S>D
 D/
TACQ 2!
TACQ q2@
   
2 noop
S>D
 D/
TACQ_2 2!
TACQ q2@
   
DACMAXLONG q2@
 D-
TEMPL1 2!
TEMPL1 q2@
   
0 noop
S>D
 D>
IF
." Sampling time too long"
                                      XGOTO 0
THEN
TACQ q2@
DROP
TACQ_INT !
RFNUM @
2* RF_LENGTH +
@
TSEL90 !
TSEL90 @
TSEL180 !
NO_VIEWS_2 @
   
1 noop
 =
IF
 [ 56832 ,code 71 ,code 56832 ,code 0 ,code  ]
BW_OVERRIDE 2!
 ELSE
 [ 56832 ,code 100 ,code 56832 ,code 0 ,code  ]
BW_OVERRIDE 2!
THEN
BW_OVERRIDE q2@
   
RFNUM @
2* RF_BWDTH +
@
S>D
 D*
   
 [ 56832 ,code 100 ,code 56832 ,code 0 ,code  ]
 D/
TEMPL1 2!
TEMPL1 q2@
DROP
PULSE_BWDTH !
14 noop
CHESS_RFNUM !
T_CHESS_GAUSS @
   
10 noop
 [ 45207 ,code 48662 ,code ] swapdrop
CHESS_RFNUM @
2* RWT +
!
BATCH_SLICES @
   
0 noop
 =
IF
NO_SLICES @
BATCH_SLICES !
THEN
NO_SLICES @
   
BATCH_SLICES @
 n/rem
   
0 noop
 !=
IF
." No of slices should be an integer number of batch size"
 CR
                                      XGOTO 0
THEN
RFNUM_SAT @
2* RF_LENGTH +
@
TSEL_SAT !
RFNUM_SAT @
2* RF_BWDTH +
@
SAT_PULSE_BWDTH !
[ 56832 ,code 170 ,code ] 15 far@
INTTOLONG
   
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D*
TSELMTCL 2!
17 noop
MTC_RFNUM !
[ 56832 ,code 170 ,code ] 15 far@
   
10 noop
 [ 45207 ,code 48662 ,code ] swapdrop
MTC_RFNUM @
2* RWT +
!
4 noop
   
[ 56832 ,code 78 ,code ] 15 far@
 [ 45207 ,code 48662 ,code ] swapdrop
TREF !
[ 56832 ,code 78 ,code ] 15 far@
TDP !
3 noop
   
OVERSAMPLE @
 +
GR_OVERSAMPLE !
3 noop
   
OVERSAMPLE @
 -
GR_UNDERSAMPLE !
3 noop
   
OVERSAMPLE2 @
 +
GP_OVERSAMPLE !
3 noop
   
OVERSAMPLE2 @
 -
GP_UNDERSAMPLE !
1 noop
   
OVERSAMPLE3 @
 +
GP2_OVERSAMPLE !
FOVF @
   
8 noop
 !=
IF
OVERSAMPLE2 @
   
0 noop
 !=
IF
." Can't do phase oversampling with rect FOV - adjust FOVf!"
                                      XGOTO 0
THEN
FOVF @
GP_OVERSAMPLE !
8 noop
GP_UNDERSAMPLE !
THEN
0 noop
GP_MUL !
 [ 56832 ,code 4000 ,code ]
GR_OVERSAMPLE @
GR_UNDERSAMPLE @
 */
SCALE_READ_OFF !
 [ 56832 ,code 400 ,code ]
SCALE_SLICE_OFF !
 [ 56832 ,code 4000 ,code ]
GP_OVERSAMPLE @
GP_UNDERSAMPLE @
 */
SCALE_PHASE_OFF !
GP_INIT_VAR @
S>D
TEMPL1 2!
GP_UNDERSAMPLE @
S>D
TEMPL2 2!
GP_OVERSAMPLE @
S>D
TEMPL3 2!
TEMPL1 q2@
   
TEMPL2 q2@
 D*
   
 [ 56832 ,code 2500 ,code 56832 ,code 0 ,code  ]
 D*
   
TEMPL3 q2@
 D/
TEMPL1 2!
TEMPL1 q2@
   
TDP @
   
TRAMP @
 +
S>D
 D/
TEMPL1 2!
TEMPL1 q2@
   
 [ 56832 ,code -32768 ,code 56832 ,code -1 ,code  ]
 D<
   
TEMPL1 q2@
   
 [ 56832 ,code 32767 ,code 56832 ,code 0 ,code  ]
 D>
 ||
IF
." FOV too small in PE dir"
 CR
                                      XGOTO 0
THEN
TEMPL1 q2@
DROP
2 noop
NO_VIEWS @
 */
GP_INC !
 [ 56832 ,code 934 ,code 56832 ,code 0 ,code  ]
   
GS_VAR @
INTTOLONG
 D*
TEMPL1 2!
TEMPL1 q2@
   
TDP @
   
TRAMP @
 +
INTTOLONG
 D/
TEMPL2 2!
TEMPL2 q2@
   
GP2_OVERSAMPLE @
INTTOLONG
 D/
DROP
GP_SL_INC !
NO_VIEWS_2 @
INTTOLONG
   
GP_SL_INC @
INTTOLONG
 D*
   
 [ 56832 ,code 2 ,code 56832 ,code 0 ,code  ]
 D/
TEMPL3 2!
TEMPL3 q2@
   
 [ 56832 ,code -32768 ,code 56832 ,code -1 ,code  ]
 D<
   
TEMPL3 q2@
   
 [ 56832 ,code 32767 ,code 56832 ,code 0 ,code  ]
 D>
 ||
IF
." FOV too small in slice direction"
                                      XGOTO 0
THEN
TEMPL3 q2@
DROP
GP_SL_INIT_VAR !
GS_VAR @
GS_VAR1 !
NO_VIEWS_2 @
   
1 noop
 >
IF
GS_VAR @
 [ 56832 ,code 100 ,code ]
SLAB_RATIO @
 */
GS_VAR1 !
THEN
GS_VAR1 @
S>D
TEMPL1 2!
TEMPL1 q2@
   
PULSE_BWDTH @
S>D
 D*
TEMPL1 2!
TEMPL1 q2@
   
 [ 56832 ,code 1070 ,code 56832 ,code 0 ,code  ]
 D/
TEMPL1 2!
DACMAXLONG q2@
   
TEMPL1 q2@
 D+
DROP
RET !
RET @
   
0 noop
 <
IF
."  Slice thickness too small for pulse selected "
                                      XGOTO 0
THEN
TEMPL1 q2@
DROP
GS_VAR_RESCALE !
TACQ q2@
   
TRAMP @
INTTOLONG
 D+
   
2 noop
S>D
 D/
TEMPL1 2!
TEMPL1 q2@
   
GR_VAR @
INTTOLONG
 D*
TEMPL1 2!
TEMPL1 q2@
   
TDP @
   
TRAMP @
 +
INTTOLONG
 D/
TEMPL1 2!
GR_UNDERSAMPLE @
S>D
TEMPL2 2!
GR_OVERSAMPLE @
S>D
TEMPL3 2!
TEMPL1 q2@
   
TEMPL2 q2@
 D*
   
TEMPL3 q2@
 D/
TEMPL4 2!
DACMAXLONG q2@
   
TEMPL4 q2@
 D+
DROP
RET !
RET @
   
0 noop
 <
IF
." FOV too small for read comp"
 CR
                                      XGOTO 0
THEN
TEMPL4 q2@
DROP
GR_COMP !
FLOW_COMP_ON @
IF
3 noop
   
TRAMP @
 [ 45207 ,code 48662 ,code ] swapdrop
   
2 noop
 /
INTTOLONG
TEMPL1 2!
TEMPL1 q2@
   
TACQ_2 q2@
 D+
   
TDP @
INTTOLONG
 D+
TEMPL1 2!
TEMPL1 q2@
   
GR_VAR @
INTTOLONG
 D*
TEMPL1 2!
TEMPL1 q2@
   
TSEL90 @
   
2 noop
 /
   
TRAMP @
 +
INTTOLONG
 D/
TEMPL1 2!
GR_UNDERSAMPLE @
S>D
TEMPL2 2!
GR_OVERSAMPLE @
S>D
TEMPL3 2!
TEMPL1 q2@
   
TEMPL2 q2@
 D*
   
TEMPL3 q2@
 D/
TEMPL4 2!
DACMAXLONG q2@
   
TEMPL4 q2@
 D+
DROP
RET !
RET @
   
0 noop
 <
IF
." Flow comp grad amp caused overflow"
 CR
                                      XGOTO 0
THEN
THEN
TEMPL4 q2@
DROP
GR_COMP_FLOW !
TSEL90 @
   
TRAMP @
 +
   
2 noop
 /
S>D
TEMPL1 2!
TREF @
   
TRAMP @
 +
S>D
TEMPL2 2!
GS_VAR_RESCALE @
S>D
TEMPL1 q2@
 D*
   
TEMPL2 q2@
 D/
TEMPL1 2!
DACMAXLONG q2@
   
TEMPL1 q2@
 D+
DROP
RET !
RET @
   
0 noop
 <
IF
." Slice refocussing lobe is excessive"
 CR
." Decrease bw or select a longer pulse"
 CR
                                      XGOTO 0
THEN
TEMPL1 q2@
DROP
GS_COMP !
[ 56832 ,code 138 ,code ] 15 far@
   
1 noop
 =
IF
                                      XGOTO 14
THEN
0 noop
NO_PB !
[ 56832 ,code 82 ,code ] 15 far@
   
1 noop
 =
   
SAT_MODE @
   
0 noop
 =
 &&
IF
0 noop
PB_INDEX !
BEGIN
NO_PB @
   
PB_INDEX @
2* PB_ON +
@
 +
NO_PB !
PB_INDEX @
2* PB_ON +
@
   
0 noop
 >
IF
PB_INDEX @
2* PB_THK +
@
SAT_FOV_SCALE !
PB_INDEX @
2* PB_OFFSET +
@
SAT_OFFSET !
PB_INDEX @
   
3 noop
 >
IF
PB_INDEX @
2* PB_OFFSET +
@
 0-
SAT_OFFSET !
THEN
PB_INDEX @
2* PB_CHANNEL +
@
SAT_CHANNEL !
 [ 56832 ,code -32768 ,code 56832 ,code -1 ,code  ]
   
SAT_PULSE_BWDTH @
S>D
 D*
TEMPL1 2!
SAT_FOV_SCALE @
S>D
 [ 56832 ,code 1 ,code 56832 ,code 0 ,code  ]
 D*
TEMPL2 2!
TEMPL2 q2@
   
GRAD_VARL q2@
 D*
TEMPL2 2!
TEMPL1 q2@
   
TEMPL2 q2@
 D/
TEMPL4 2!
DACMAXLONG q2@
   
TEMPL4 q2@
 D+
DROP
RET !
RET @
   
0 noop
 <
IF
." PB ["
PB_INDEX @
   
1 noop
 +
 .
." ] thk too small!"
 CR
                                      XGOTO 0
THEN
TEMPL4 q2@
DROP
GS_SAT !
TEMPL4 q2@
DROP
PB_INDEX @
2* PB_GS_SAT +
!
NO_SLICES @
SLICE_INTERLEAVE @
CURRENT_SLICE @
   
1 noop
 -
ORDERTIMETOPOS
POS_INDEX !
 [ 56832 ,code 1 ,code 56832 ,code 0 ,code  ]
   
SAT_OFFSET @
S>D
 D*
   
SAT_PULSE_BWDTH @
S>D
 D*
TEMPL1 2!
0 noop
S>D
TEMPL2 2!
TEMPL2 q2@
   
TEMPL1 q2@
 D+
   
SAT_FOV_SCALE @
S>D
 D/
SAT_SLICE_FREQ_LONG 2!
SAT_SLICE_FREQ_LONG q2@
DROP
FOV_SAT_SLICE_FREQ !
0 noop
KHZ_NEW3 !
0 noop
HZ_NEW3 !
SAT_SLICE_FREQ_LONG q2@
   
 [ 56832 ,code -32767 ,code 56832 ,code -1 ,code  ]
 D<
   
SAT_SLICE_FREQ_LONG q2@
   
 [ 56832 ,code 32767 ,code 56832 ,code 0 ,code  ]
 D>
 OR
IF
SAT_SLICE_FREQ_LONG q2@
   
 [ 56832 ,code 32767 ,code 56832 ,code 0 ,code  ]
 D/REM
DROP
FOV_SAT_SLICE_FREQ !
 [ 56832 ,code 32 ,code ]
S>D
SAT_SLICE_FREQ_LONG q2@
   
 [ 56832 ,code 32767 ,code ]
S>D
 D/
 D*
DROP
KHZ_NEW3 !
 [ 56832 ,code 767 ,code ]
S>D
SAT_SLICE_FREQ_LONG q2@
   
 [ 56832 ,code 32767 ,code ]
S>D
 D/
 D*
DROP
HZ_NEW3 !
THEN
KHZ_NEW3 @
PB_INDEX @
2* PB_KHZ +
!
HZ_NEW3 @
PB_INDEX @
2* PB_HZ +
!
FOV_SAT_SLICE_FREQ @
PB_INDEX @
2* PB_FREQ +
!
[ 56832 ,code 8 ,code ] 15 far@
IF
." PB ["
PB_INDEX @
 .
." ], gs_sat = "
GS_SAT @
 .
."   sat_freq = "
FOV_SAT_SLICE_FREQ @
 .
 CR
THEN
THEN
PB_INDEX @
   
1 noop
 +
PB_INDEX !
PB_INDEX @
   
6 noop
 =
 UNTIL
THEN
LABEL 14
[ 56832 ,code 8 ,code ] 15 far@
IF
." No of PBs = "
NO_PB @
 .
 CR
THEN
DIXON_ON @
IF
SMODE @
   
3 noop
 <
IF
SMODE @
   
DELTA_2_90 @
 [ 45207 ,code 48662 ,code ] swapdrop
DELTA_2 !
THEN
SMODE @
   
3 noop
 =
IF
NO_EXPERIMENTS @
   
3 noop
 <
IF
." Number of experiments must be 3 in W-F mode!"
                                      XGOTO 0
THEN
THEN
THEN
TR_ARRAY_SIZE @
   
0 noop
 >
IF
NO_EXPERIMENTS @
   
TR_ARRAY_SIZE @
 n/rem
   
0 noop
 !=
IF
." Exper array size ("
NO_EXPERIMENTS @
 .
." ) must be divisable by the TR array size ("
TR_ARRAY_SIZE @
 .
." )!"
 CR
                                      XGOTO 0
THEN
0 noop
2* TR_ARRAY +
@
[ 56832 ,code 2 ,code ] 15 far!
THEN
0 noop
2* GRAD_VAR +
@
UNSIGNEDTOLONG
   
2 noop
S>D
 D/
DROP
0 noop
2* GRAD_VAR_L +
!
1 noop
2* GRAD_VAR +
@
UNSIGNEDTOLONG
   
2 noop
S>D
 D/
DROP
1 noop
2* GRAD_VAR_L +
!
2 noop
2* GRAD_VAR +
@
UNSIGNEDTOLONG
   
2 noop
S>D
 D/
DROP
2 noop
2* GRAD_VAR_L +
!
3 noop
2* GRAD_VAR +
@
UNSIGNEDTOLONG
   
2 noop
S>D
 D/
DROP
3 noop
2* GRAD_VAR_L +
!
[ 56832 ,code 20 ,code ] 15 far@
[ 56832 ,code 18 ,code ] 15 far@
[ 56832 ,code 16 ,code ] 15 far@
3 noop
2* GRAD_VAR_L +
@
0 noop
2* GRAD_VAR_L +
@
2 noop
2* GRAD_VAR_L +
@
0 noop
2* GRAD_VAR_L +
@
1 noop
2* GRAD_VAR_L +
@
0 noop
2* GRAD_VAR_L +
@
MR3040_CREATEBASEMATRIX
TEMP_MAC !
TEMP_MAC @
IF
." Could not create base matrix, status = "
TEMP_MAC @
 .
 CR
                                      XGOTO 0
THEN
[ 56832 ,code 99 ,code ] us
0 noop
0 noop
 [ 56832 ,code -232 ,code ]
Set_board_Multipliers
0 noop
0 noop
 [ 56832 ,code -240 ,code ]
Set_board_Multipliers
8 noop
20 noop
 [ 56832 ,code -236 ,code ]
 [ 56832 ,code -228 ,code ]
Set_addr_and_waits
 [ 56832 ,code -236 ,code ]
Append_Boards_Ready
 [ 56832 ,code -228 ,code ]
Append_Boards_Ready
MR3031_GO
0 noop
MR3040_SETLISTADDRESS
MR3040_INITLIST
TEMP_3040 !
0 noop
 [ 56832 ,code 130 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
 [ 56832 ,code 255 ,code ]
0 noop
0 noop
0 noop
CREATEMATRIXTEST
IF
                                      XGOTO 0
THEN
[ 56832 ,code 99 ,code ] us
 [ 56832 ,code 511 ,code ]
0 noop
0 noop
0 noop
CREATEMATRIXTEST
IF
                                      XGOTO 0
THEN
[ 56832 ,code 99 ,code ] us
TEMP_3040 @
 [ 56832 ,code 546 ,code ]
MR3040_SETLIST
 [ 56832 ,code 255 ,code ]
MR3040_SELECTMATRIX
 [ 56832 ,code 546 ,code ]
MR3040_START
[ 56832 ,code 999 ,code ] us
TRAMP @
   
5 noop
 /
CLOCK !
CLOCK @
MR3040_CLOCK
DIFF_TRAMP @
   
5 noop
 /
DIFF_CLOCK !
DIFF_CLOCK @
MR3040_CLOCK
0 noop
MR3040_SETLISTADDRESS
MR3040_INITLIST
SLICE_LIST !
0 noop
0 noop
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
0 noop
MR3040_HOLD
0 noop
13 noop
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
0 noop
 [ 56832 ,code 156 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
TREF @
CLOCK @
 [ 56832 ,code 117 ,code ]
MR3040_DELAY
0 noop
 [ 56832 ,code 117 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
MR3040_INITLIST
READ_PRE_LIST !
0 noop
 [ 56832 ,code 130 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
0 noop
MR3040_HOLD
0 noop
 [ 56832 ,code 130 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
FLOW_COMP_ON @
IF
0 noop
 [ 56832 ,code 143 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
TREF @
CLOCK @
 [ 56832 ,code 65 ,code ]
MR3040_DELAY
0 noop
 [ 56832 ,code 65 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
0 noop
26 noop
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
TSEL90 @
   
2 noop
 /
CLOCK @
 [ 56832 ,code 39 ,code ]
MR3040_DELAY
0 noop
 [ 56832 ,code 39 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
THEN
FLOW_COMP_ON @
   
0 noop
 =
IF
0 noop
 [ 56832 ,code 156 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
TREF @
CLOCK @
 [ 56832 ,code 117 ,code ]
MR3040_DELAY
0 noop
 [ 56832 ,code 117 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
THEN
MR3040_INITLIST
SLICE_180_REFOCUS !
0 noop
0 noop
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
TSEL90 @
   
[ 56832 ,code 12 ,code ] 15 far@
 +
   
[ 56832 ,code 12 ,code ] 15 far@
 +
CLOCK @
13 noop
MR3040_DELAY
0 noop
13 noop
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
MR3040_INITLIST
SLICE_180_CRUSH !
0 noop
 [ 56832 ,code 143 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
TDP @
CLOCK @
 [ 56832 ,code 65 ,code ]
MR3040_DELAY
0 noop
 [ 56832 ,code 65 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
CLOCK @
MR3040_CLOCK
MR3040_INITLIST
DIFF_LIST !
0 noop
0 noop
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
0 noop
MR3040_HOLD
0 noop
13 noop
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
DIFF_CLOCK @
MR3040_CLOCK
MR3040_INITLIST
DIFF_LIST2 !
0 noop
0 noop
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
0 noop
MR3040_HOLD
0 noop
13 noop
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
MR3040_INITLIST
READ_LIST !
0 noop
 [ 56832 ,code 156 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
TDP @
CLOCK @
 [ 56832 ,code 117 ,code ]
MR3040_DELAY
0 noop
 [ 56832 ,code 117 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
0 noop
0 noop
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
TACQ_INT @
CLOCK @
13 noop
MR3040_DELAY
0 noop
13 noop
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
0 noop
 [ 56832 ,code 156 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
TDP @
CLOCK @
 [ 56832 ,code 117 ,code ]
MR3040_DELAY
0 noop
 [ 56832 ,code 117 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
MR3040_INITLIST
PHASE_LIST !
0 noop
 [ 56832 ,code 156 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
TDP @
CLOCK @
 [ 56832 ,code 117 ,code ]
MR3040_DELAY
0 noop
 [ 56832 ,code 117 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
TRAMP @
CLOCK @
0 noop
MR3040_DELAY
TACQ_INT @
CLOCK @
0 noop
MR3040_DELAY
TRAMP @
CLOCK @
0 noop
MR3040_DELAY
0 noop
 [ 56832 ,code 143 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
TDP @
CLOCK @
 [ 56832 ,code 65 ,code ]
MR3040_DELAY
0 noop
 [ 56832 ,code 65 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
MR3040_INITLIST
SLICE_LIST_RP !
0 noop
 [ 56832 ,code 143 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
TDP @
CLOCK @
 [ 56832 ,code 65 ,code ]
MR3040_DELAY
0 noop
 [ 56832 ,code 65 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
TRAMP @
CLOCK @
0 noop
MR3040_DELAY
TACQ_INT @
CLOCK @
0 noop
MR3040_DELAY
TRAMP @
CLOCK @
0 noop
MR3040_DELAY
0 noop
 [ 56832 ,code 143 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
TDP @
CLOCK @
 [ 56832 ,code 65 ,code ]
MR3040_DELAY
0 noop
 [ 56832 ,code 65 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
MR3040_INITLIST
SAT_LIST !
0 noop
0 noop
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
0 noop
MR3040_HOLD
0 noop
 [ 56832 ,code 52 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
0 noop
MR3040_HOLD
0 noop
 [ 56832 ,code 65 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
MR3040_INITLIST
POST_CRUSH_LIST !
0 noop
0 noop
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
[ 56832 ,code 98 ,code ] 15 far@
CLOCK @
13 noop
MR3040_DELAY
0 noop
13 noop
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
DE_ON @
IF
MR3040_INITLIST
SLICE_DE90_LIST !
FLOW_COMP_ON @
IF
TSEL90 @
   
2 noop
 /
   
2 noop
   
TRAMP @
 [ 45207 ,code 48662 ,code ] swapdrop
 +
CLOCK @
 [ 56832 ,code 130 ,code ]
MR3040_DELAY
THEN
0 noop
 [ 56832 ,code 156 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
TREF @
CLOCK @
 [ 56832 ,code 117 ,code ]
MR3040_DELAY
0 noop
 [ 56832 ,code 117 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
0 noop
0 noop
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
0 noop
MR3040_HOLD
0 noop
13 noop
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
MR3040_INITLIST
READ_DE90_LIST !
FLOW_COMP_ON @
IF
0 noop
26 noop
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
TSEL90 @
   
2 noop
 /
CLOCK @
 [ 56832 ,code 39 ,code ]
MR3040_DELAY
0 noop
 [ 56832 ,code 39 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
0 noop
 [ 56832 ,code 143 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
TREF @
CLOCK @
 [ 56832 ,code 65 ,code ]
MR3040_DELAY
0 noop
 [ 56832 ,code 65 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
THEN
FLOW_COMP_ON @
   
0 noop
 =
IF
0 noop
 [ 56832 ,code 156 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
TREF @
CLOCK @
 [ 56832 ,code 117 ,code ]
MR3040_DELAY
0 noop
 [ 56832 ,code 117 ,code ]
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
THEN
THEN
MR3040_INITLIST
CHESS_LIST !
0 noop
0 noop
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
[ 56832 ,code 116 ,code ] 15 far@
CLOCK @
13 noop
MR3040_DELAY
0 noop
13 noop
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
MR3040_INITLIST
MTC_LIST !
0 noop
0 noop
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
[ 56832 ,code 172 ,code ] 15 far@
CLOCK @
13 noop
MR3040_DELAY
0 noop
13 noop
 [ 56832 ,code 50 ,code ]
1 noop
MR3040_OUTPUT
1 noop
0 noop
0 noop
0 noop
CREATEMATRIXTEST
IF
                                      XGOTO 0
THEN
[ 56832 ,code 99 ,code ] us
[ 56832 ,code 138 ,code ] 15 far@
   
1 noop
 =
IF
                                      XGOTO 15
THEN
[ 56832 ,code 34 ,code ] 15 far@
   
T_RESP_PLATEAU @
   
0 noop
 =
 &&
IF
0 noop
[ 56832 ,code 102 ,code ] 15 far!
0 noop
[ 56832 ,code 104 ,code ] 15 far!
0 noop
CNT !
LABEL 16
0 noop
TEMP !
LABEL 17
HOSTREQUEST
drop
0 noop
S>D
TEMPL1 2!
BEGIN
 [ 56832 ,code 921 ,code 56832 ,code 0 ,code  ]
DELAY32
TEMPL1 q2@
   
 [ 56832 ,code 1 ,code 56832 ,code 0 ,code  ]
 D+
TEMPL1 2!
[ 56832 ,code 1 ,code ] 24G@SWAPAND
   
0 noop
 !=
   
TEMPL1 q2@
   
 [ 56832 ,code -15536 ,code 56832 ,code 0 ,code  ]
 D>
 ||
 UNTIL
TEMPL1 q2@
   
 [ 56832 ,code 2 ,code 56832 ,code 0 ,code  ]
 D<
IF
TEMP @
   
1 noop
 +
TEMP !
TEMP @
   
10 noop
 <
IF
XGOTO 17
 ELSE
." 10 attempts and the gate still high"
 CR
THEN
THEN
TEMPL1 q2@
   
 [ 56832 ,code -15536 ,code 56832 ,code 0 ,code  ]
 D< NOT
IF
." No gate detected for 5 seconds, disabling gating"
 CR
0 noop
[ 56832 ,code 34 ,code ] 15 far!
 ELSE
TEMPL1 q2@
   
 [ 56832 ,code 10 ,code 56832 ,code 0 ,code  ]
 D/
DROP
CNT @
2* GATING_TEMP2 +
!
0 noop
S>D
TEMPL1 2!
BEGIN
 [ 56832 ,code 921 ,code 56832 ,code 0 ,code  ]
DELAY32
TEMPL1 q2@
   
 [ 56832 ,code 1 ,code 56832 ,code 0 ,code  ]
 D+
TEMPL1 2!
[ 56832 ,code 1 ,code ] 24G@SWAPAND
   
0 noop
 =
   
TEMPL1 q2@
   
 [ 56832 ,code -15536 ,code 56832 ,code 0 ,code  ]
 D>
 ||
 UNTIL
TEMPL1 q2@
   
 [ 56832 ,code -15536 ,code 56832 ,code 0 ,code  ]
 D< NOT
IF
." Gate too long (>=5s)"
 CR
 ELSE
TEMPL1 q2@
   
 [ 56832 ,code 10 ,code 56832 ,code 0 ,code  ]
 D/
DROP
CNT @
2* GATING_TEMP1 +
!
CNT @
   
1 noop
 +
CNT !
THEN
CNT @
   
6 noop
 <
IF
XGOTO 16
 ELSE
1 noop
CNT !
4 noop
FOR
[ 56832 ,code 102 ,code ] 15 far@
   
CNT @
2* GATING_TEMP1 +
@
 +
[ 56832 ,code 102 ,code ] 15 far!
[ 56832 ,code 104 ,code ] 15 far@
   
CNT @
2* GATING_TEMP2 +
@
 +
[ 56832 ,code 104 ,code ] 15 far!
CNT @
   
1 noop
 +
CNT !
 NEXT
[ 56832 ,code 102 ,code ] 15 far@
   
5 noop
 /
[ 56832 ,code 102 ,code ] 15 far!
[ 56832 ,code 104 ,code ] 15 far@
   
5 noop
 /
[ 56832 ,code 104 ,code ] 15 far!
." Average gate duration (N=5) = "
[ 56832 ,code 102 ,code ] 15 far@
 .
."  ms"
 CR
." Average gate interval (N=5) = "
[ 56832 ,code 104 ,code ] 15 far@
 .
."  ms"
 CR
THEN
THEN
THEN
T_RESP_PLATEAU @
   
0 noop
 =
IF
[ 56832 ,code 104 ,code ] 15 far@
T_RESP_FRACTION @
 [ 56832 ,code 100 ,code ]
 */
T_RESP_PLATEAU !
[ 56832 ,code 34 ,code ] 15 far@
IF
." Plateau duration assuming "
T_RESP_FRACTION @
 .
." pc interval fraction = "
T_RESP_PLATEAU @
 .
."  ms"
 CR
THEN
THEN
0 noop
[ 56832 ,code 146 ,code ] 15 far!
0 noop
PHASE_REC !
 [ 56832 ,code 100 ,code ]
SETSYNC
SYNC
STARTTIMER
0 noop
COMPLETED_EX !
0 noop
[ 56832 ,code 142 ,code ] 15 far!
LABEL 18
DIXON_ON @
   
1 noop
 =
   
SMODE @
   
3 noop
 =
 &&
IF
COMPLETED_EX @
   
DELTA_2_90 @
 [ 45207 ,code 48662 ,code ] swapdrop
   
DELTA_0 @
 -
DELTA_2 !
THEN
TR_ARRAY_SIZE @
   
0 noop
 >
IF
COMPLETED_EX @
   
TR_ARRAY_SIZE @
 n/rem
TEMP !
TEMP @
2* TR_ARRAY +
@
[ 56832 ,code 2 ,code ] 15 far!
THEN
0 noop
B_STEP_CNT !
LABEL 19
B_STEP_CNT @
2* B_GRADS_ARRAY +
@
[ 56832 ,code 188 ,code ] 15 far@
 [ 56832 ,code 100 ,code ]
 */
DIFF_GRAD !
[ 56832 ,code 8 ,code ] 15 far@
IF
." diff_grad = "
DIFF_GRAD @
 .
 CR
THEN
[ 56832 ,code 180 ,code ] 15 far@
   
0 noop
 >
   
DIFF_GRAD @
   
 [ 56832 ,code 30000 ,code ]
 >
 &&
IF
." Diffusion gradient amp "
DIFF_GRAD @
 .
." DAC is too high"
 CR
                                      XGOTO 0
THEN
0 noop
DIFF_DIR_CNT !
LABEL 20
[ 56832 ,code 180 ,code ] 15 far@
   
1 noop
 =
IF
[ 56832 ,code 184 ,code ] 15 far@
   
[ 56832 ,code 12 ,code ] 15 far@
 <
IF
." diff_tcrush "
[ 56832 ,code 184 ,code ] 15 far@
 .
."  is bigger than tcrush "
[ 56832 ,code 12 ,code ] 15 far@
 .
 CR
THEN
THEN
[ 56832 ,code 12 ,code ] 15 far@
[ 56832 ,code 186 ,code ] 15 far!
0 noop
[ 56832 ,code 182 ,code ] 15 far!
[ 56832 ,code 180 ,code ] 15 far@
   
DIFF_GRAD @
DIFF_DIR_CNT @
   
3 noop
 [ 45207 ,code 48662 ,code ] swapdrop
2* DIFF_GRAD_DIR +
@
 [ 56832 ,code 1000 ,code ]
 */
 [ 45207 ,code 48662 ,code ] swapdrop
DIFF_READ !
[ 56832 ,code 180 ,code ] 15 far@
   
DIFF_GRAD @
DIFF_DIR_CNT @
   
3 noop
 [ 45207 ,code 48662 ,code ] swapdrop
   
1 noop
 +
2* DIFF_GRAD_DIR +
@
 [ 56832 ,code 1000 ,code ]
 */
 [ 45207 ,code 48662 ,code ] swapdrop
DIFF_PHASE !
[ 56832 ,code 180 ,code ] 15 far@
   
DIFF_GRAD @
DIFF_DIR_CNT @
   
3 noop
 [ 45207 ,code 48662 ,code ] swapdrop
   
2 noop
 +
2* DIFF_GRAD_DIR +
@
 [ 56832 ,code 1000 ,code ]
 */
 [ 45207 ,code 48662 ,code ] swapdrop
DIFF_SLICE !
DIFF_READ @
   
0 noop
 !=
   
DIFF_PHASE @
   
0 noop
 !=
 ||
   
DIFF_SLICE @
   
0 noop
 !=
 ||
IF
[ 56832 ,code 184 ,code ] 15 far@
[ 56832 ,code 186 ,code ] 15 far!
1 noop
[ 56832 ,code 182 ,code ] 15 far!
THEN
[ 56832 ,code 138 ,code ] 15 far@
   
1 noop
 =
IF
[ 56832 ,code 184 ,code ] 15 far@
[ 56832 ,code 186 ,code ] 15 far!
[ 56832 ,code 180 ,code ] 15 far@
[ 56832 ,code 182 ,code ] 15 far!
THEN
0 noop
IMAGE_AV !
LABEL 15
0 noop
SLICE_BATCH_START !
LABEL 21
0 noop
GP_LOC !
LABEL 22
0 noop
CURRENT_VIEW !
0 noop
GP_LOC !
1 noop
NAV_CNT !
NAV_ON @
   
1 noop
 =
IF
0 noop
NAV_CNT !
THEN
LABEL 23
0 noop
VIEW_AV !
0 noop
CURRENT_VIEW_2 !
LABEL 24
LABEL 25
SLICE_BATCH_START @
CURRENT_SLICE !
LABEL 26
CURRENT_SLICE @
   
1 noop
 +
CURRENT_SLICE !
0 noop
SLICE_AV !
VIEW_AV @
   
IMAGE_AV @
 +
NO_ACQ !
BATCH_INTERLEAVE @
NO_SLICES @
SLICE_INTERLEAVE @
BATCH_SLICES @
CURRENT_SLICE @
   
1 noop
 -
BATCHTIMETOPOS
POS_INDEX !
SCALE_READ_OFF @
S>D
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D/
TEMP_MAC_LONG 2!
TEMP_MAC_LONG q2@
   
SAMPLE_PERIOD @
S>D
 D*
TEMP_MAC_LONG 2!
POS_INDEX @
2* FOV_READ_OFF +
@
S>D
 [ 56832 ,code 10000 ,code 56832 ,code 0 ,code  ]
 D*
READ_FREQ_LONG 2!
READ_FREQ_LONG q2@
   
TEMP_MAC_LONG q2@
 D/
READ_FREQ_LONG 2!
READ_FREQ_LONG q2@
DROP
FOV_READ_FREQ !
0 noop
KHZ_NEW2 !
0 noop
HZ_NEW2 !
READ_FREQ_LONG q2@
   
 [ 56832 ,code -32767 ,code 56832 ,code -1 ,code  ]
 D<
   
READ_FREQ_LONG q2@
   
 [ 56832 ,code 32767 ,code 56832 ,code 0 ,code  ]
 D>
 OR
IF
READ_FREQ_LONG q2@
   
 [ 56832 ,code 32767 ,code 56832 ,code 0 ,code  ]
 D/
TEMP_MAC_LONG 2!
 [ 56832 ,code 32 ,code ]
S>D
TEMP_MAC_LONG q2@
 D*
DROP
KHZ_NEW2 !
 [ 56832 ,code 767 ,code ]
S>D
TEMP_MAC_LONG q2@
 D*
DROP
HZ_NEW2 !
READ_FREQ_LONG q2@
   
TEMP_MAC_LONG q2@
   
 [ 56832 ,code 32767 ,code 56832 ,code 0 ,code  ]
 D*
 D-
DROP
FOV_READ_FREQ !
THEN
SCALE_PHASE_OFF @
PHASE_RES @
 [ 56832 ,code 1000 ,code ]
 */
TEMP_MAC !
POS_INDEX @
2* FOV_PHASE_OFF +
@
 [ 56832 ,code 360 ,code ]
TEMP_MAC @
 */
FOV_PHASE_DEG !
FOV_PHASE_DEG @
   
0 noop
 <
IF
FOV_PHASE_DEG @
   
 [ 56832 ,code 360 ,code ]
 [ 56832 ,code 1000 ,code ]
PHASE_RES @
 */
 +
FOV_PHASE_DEG !
THEN
[ 56832 ,code 136 ,code ] 15 far@
INTTOLONG
   
PULSE_BWDTH @
INTTOLONG
 D*
   
10 noop
S>D
 D/
   
1 noop
S>D
 D/
SLICE_FREQ_VAR 2!
POS_INDEX @
2* FOV_SLICE_OFF +
@
S>D
PULSE_BWDTH @
INTTOLONG
 D*
   
SCALE_SLICE_OFF @
INTTOLONG
 D/
SLICE_FREQ_LONG 2!
SLICE_FREQ_LONG q2@
   
SLICE_FREQ_VAR q2@
 D+
SLICE_FREQ_LONG 2!
SLICE_FREQ_LONG q2@
DROP
FOV_SLICE_FREQ !
0 noop
KHZ_NEW !
0 noop
HZ_NEW !
SLICE_FREQ_LONG q2@
   
 [ 56832 ,code -32767 ,code 56832 ,code -1 ,code  ]
 D<
   
SLICE_FREQ_LONG q2@
   
 [ 56832 ,code 32767 ,code 56832 ,code 0 ,code  ]
 D>
 OR
IF
SLICE_FREQ_LONG q2@
   
 [ 56832 ,code 32767 ,code ]
S>D
 D/
TEMPL1 2!
SLICE_FREQ_LONG q2@
   
TEMPL1 q2@
   
 [ 56832 ,code 32767 ,code 56832 ,code 0 ,code  ]
 D*
 D-
DROP
FOV_SLICE_FREQ !
 [ 56832 ,code 32 ,code ]
S>D
TEMPL1 q2@
 D*
DROP
KHZ_NEW !
 [ 56832 ,code 767 ,code ]
S>D
TEMPL1 q2@
 D*
DROP
HZ_NEW !
THEN
0 noop
S>D
SLICE_FREQ_VAR 2!
POS_INDEX @
2* FOV_SLICE_OFF +
@
FOV_SL_PHASE_OFF !
FOV_SL_PHASE_OFF @
   
GP2_OVERSAMPLE @
 /
FOV_SL_PHASE_OFF !
FOV_SL_PHASE_OFF @
SLAB_RATIO @
 [ 56832 ,code 100 ,code ]
 */
FOV_SL_PHASE_OFF !
SCALE_SLICE_OFF @
PHASE_RES @
 [ 56832 ,code 1000 ,code ]
 */
TEMP !
FOV_SL_PHASE_OFF @
[ 56832 ,code 150 ,code ] 15 far@
   
 [ 56832 ,code 360 ,code ]
 [ 45207 ,code 48662 ,code ] swapdrop
TEMP @
 */
FOV_SL_PHASE_DEG !
FOV_SL_PHASE_DEG @
   
0 noop
 <
IF
FOV_SL_PHASE_DEG @
   
 [ 56832 ,code 360 ,code ]
 [ 56832 ,code 1000 ,code ]
PHASE_RES @
 */
 +
FOV_SL_PHASE_DEG !
THEN
NO_ACQ @
PHASE_CYCLE @
AQPHASE
   
DEG_90 @
 [ 45207 ,code 48662 ,code ] swapdrop
PHASE_90 !
PHASE_90 @
   
3 noop
   
DEG_90 @
 [ 45207 ,code 48662 ,code ] swapdrop
 +
PHASE_180 !
FOV_READ_FREQ @
   
[ 56832 ,code 32 ,code ] 15 far@
 +
S>D
TEMPL3 2!
TEMPL3 q2@
   
DACMAXLONG q2@
 D+
   
0 noop
S>D
 D<
   
TEMPL3 q2@
   
DACMAXLONG q2@
 D-
   
0 noop
S>D
 D>
 OR
IF
." Reduce receive frequency"
 CR
                                      XGOTO 0
THEN
[ 56832 ,code 124 ,code ] 15 far@
IF
4 noop
FREQUENCY_BUFFER
[ 56832 ,code 24 ,code ] 15 far@
[ 56832 ,code 26 ,code ] 15 far@
[ 56832 ,code 28 ,code ] 15 far@
[ 56832 ,code 30 ,code ] 15 far@
FREQUENCY
[ 56832 ,code 122 ,code ] 15 far@
OFFSET_FREQUENCY
THEN
[ 56832 ,code 160 ,code ] 15 far@
IF
5 noop
FREQUENCY_BUFFER
[ 56832 ,code 24 ,code ] 15 far@
[ 56832 ,code 26 ,code ] 15 far@
[ 56832 ,code 28 ,code ] 15 far@
[ 56832 ,code 30 ,code ] 15 far@
FREQUENCY
NO_EXPERIMENTS @
   
1 noop
 >
IF
MTC_ARRAY_ON @
   
0 noop
 =
IF
MTC_FREQ_MAX @
   
MTC_FREQ_STEP @
   
COMPLETED_EX @
 [ 45207 ,code 48662 ,code ] swapdrop
 +
[ 56832 ,code 176 ,code ] 15 far!
 ELSE
COMPLETED_EX @
2* MTC_FREQ_ARRAY +
@
[ 56832 ,code 176 ,code ] 15 far!
THEN
THEN
[ 56832 ,code 176 ,code ] 15 far@
OFFSET_FREQUENCY
THEN
1 noop
FREQUENCY_BUFFER
[ 56832 ,code 24 ,code ] 15 far@
[ 56832 ,code 26 ,code ] 15 far@
   
KHZ_NEW2 @
 +
[ 56832 ,code 28 ,code ] 15 far@
   
HZ_NEW2 @
 +
[ 56832 ,code 30 ,code ] 15 far@
FREQUENCY
FOV_READ_FREQ @
   
[ 56832 ,code 32 ,code ] 15 far@
 +
OFFSET_FREQUENCY
0 noop
FREQUENCY_BUFFER
[ 56832 ,code 24 ,code ] 15 far@
[ 56832 ,code 26 ,code ] 15 far@
   
KHZ_NEW @
 +
[ 56832 ,code 28 ,code ] 15 far@
   
HZ_NEW @
 +
[ 56832 ,code 30 ,code ] 15 far@
FREQUENCY
FOV_SLICE_FREQ @
S>D
SLICE_FREQ_VAR q2@
 D+
DROP
OFFSET_FREQUENCY
RESET_FREQUENCY
LABEL 27
[ 56832 ,code 158 ,code ] 15 far@
SYSTEMOUT
[ 56832 ,code 22 ,code ] 15 far@
[ 56832 ,code 64 ,code ] 15 far@
 [ 56832 ,code 90 ,code ]
 */
[ 56832 ,code 58 ,code ] 15 far!
[ 56832 ,code 22 ,code ] 15 far@
[ 56832 ,code 62 ,code ] 15 far@
 [ 56832 ,code 100 ,code ]
 */
[ 56832 ,code 60 ,code ] 15 far!
[ 56832 ,code 58 ,code ] 15 far@
   
 [ 56832 ,code 2047 ,code ]
 >
IF
 [ 56832 ,code 2047 ,code ]
[ 56832 ,code 58 ,code ] 15 far!
THEN
[ 56832 ,code 60 ,code ] 15 far@
   
 [ 56832 ,code 2047 ,code ]
 >
IF
 [ 56832 ,code 2047 ,code ]
[ 56832 ,code 60 ,code ] 15 far!
THEN
 [ 56832 ,code 31000 ,code ]
WAITTIMER
STARTTIMER
TACQ q2@
   
 [ 56832 ,code 100 ,code ]
S>D
 D*
   
 [ 56832 ,code 200 ,code 56832 ,code 0 ,code  ]
 D/
TEMPL2 2!
TSEL90 @
   
2 noop
 /
   
TRAMP @
   
4 noop
 [ 45207 ,code 48662 ,code ] swapdrop
 +
S>D
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D+
   
TSEL180 @
   
2 noop
 /
S>D
 D+
   
[ 56832 ,code 186 ,code ] 15 far@
S>D
 D+
   
20 noop
S>D
 D+
DROP
INTTOLONG
MIN_PRE 2!
MIN_PRE q2@
   
[ 56832 ,code 182 ,code ] 15 far@
S>D
SM_DELTA_US q2@
   
DIFF_TRAMP @
INTTOLONG
 D+
 D*
 D+
MIN_PRE 2!
TSEL180 @
   
2 noop
 /
   
3 noop
   
TRAMP @
 [ 45207 ,code 48662 ,code ] swapdrop
 +
S>D
 [ 56832 ,code 500 ,code 56832 ,code 0 ,code  ]
 D+
   
[ 56832 ,code 186 ,code ] 15 far@
S>D
 D+
DROP
INTTOLONG
   
TEMPL2 q2@
 D+
   
 [ 56832 ,code 30 ,code 56832 ,code 0 ,code  ]
 D+
   
 [ 56832 ,code 1 ,code 56832 ,code 0 ,code  ]
 D+
   
 [ 56832 ,code 35 ,code 56832 ,code 0 ,code  ]
 D+
MIN_POST 2!
MIN_POST q2@
   
[ 56832 ,code 182 ,code ] 15 far@
S>D
SM_DELTA_US q2@
   
DIFF_TRAMP @
INTTOLONG
 D+
 D*
 D+
MIN_POST 2!
[ 56832 ,code 4 ,code ] 15 far@
   
0 noop
 =
IF
MIN_POST q2@
   
MIN_PRE q2@
 D>
IF
MIN_POST q2@
TRUE_HALF_TE_US 2!
THEN
MIN_PRE q2@
   
MIN_POST q2@
 D>
IF
MIN_PRE q2@
TRUE_HALF_TE_US 2!
THEN
TRUE_HALF_TE_US q2@
   
 [ 56832 ,code 2 ,code 56832 ,code 0 ,code  ]
 D*
TE_US_LONG 2!
[ 56832 ,code 182 ,code ] 15 far@
   
1 noop
 =
IF
0 noop
S>D
EXTRA_DELTA_US 2!
MIN_TE q2@
   
2 noop
S>D
EXTRA_DELTA_US q2@
 D*
 D+
MIN_TE 2!
THEN
TE_US_LONG q2@
MIN_TE 2!
TRUE_HALF_TE_US q2@
   
MIN_PRE q2@
 D-
TEMPL1 2!
TRUE_HALF_TE_US q2@
   
MIN_POST q2@
 D-
TEMPL2 2!
 ELSE
[ 56832 ,code 4 ,code ] 15 far@
INTTOLONG
   
 [ 56832 ,code 500 ,code 56832 ,code 0 ,code  ]
 D*
TRUE_HALF_TE_US 2!
 [ 56832 ,code 2 ,code 56832 ,code 0 ,code  ]
   
TRUE_HALF_TE_US q2@
 D*
TE_US_LONG 2!
TRUE_HALF_TE_US q2@
   
MIN_PRE q2@
 D-
TEMPL1 2!
TRUE_HALF_TE_US q2@
   
MIN_POST q2@
 D-
TEMPL2 2!
MIN_POST q2@
   
MIN_PRE q2@
 D< NOT
IF
MIN_POST q2@
   
 [ 56832 ,code 2 ,code 56832 ,code 0 ,code  ]
 D*
MIN_TE 2!
THEN
MIN_POST q2@
   
MIN_PRE q2@
 D<
IF
MIN_PRE q2@
   
 [ 56832 ,code 2 ,code 56832 ,code 0 ,code  ]
 D*
MIN_TE 2!
THEN
TEMPL2 q2@
   
0 noop
S>D
 D> NOT
   
TEMPL1 q2@
   
0 noop
S>D
 D> NOT
 ||
IF
." TE is too short, increase to "
MIN_TE q2@
   
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D/
   
1 noop
S>D
 D+
DROP
 .
."  ms (="
MIN_TE q2@
 D.
."  us)"
 CR
                                      XGOTO 0
THEN
THEN
[ 56832 ,code 180 ,code ] 15 far@
IF
SM_DELTA_US q2@
   
DIFF_TRAMP @
   
TSEL180 @
 +
   
2 noop
   
TRAMP @
   
[ 56832 ,code 186 ,code ] 15 far@
 +
 [ 45207 ,code 48662 ,code ] swapdrop
 +
INTTOLONG
 D+
BIG_DELTA_MIN 2!
BIG_DELTA_MIN q2@
   
TEMPL1 q2@
 D+
   
TEMPL2 q2@
 D+
BIG_DELTA_MAX_4_GIVEN_TE 2!
BIG_DELTA_US q2@
   
BIG_DELTA_MAX_4_GIVEN_TE q2@
 D>
IF
." Big delta ("
BIG_DELTA_US q2@
 D.
." ) is too big for given TE, max Big delta = "
BIG_DELTA_MAX_4_GIVEN_TE q2@
   
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D/
DROP
 .
."  ms ("
BIG_DELTA_MAX_4_GIVEN_TE q2@
 D.
."  us)"
 CR
." Either reduce Big delta or increase TE to more than min. TE"
 CR
                                      XGOTO 0
THEN
BIG_DELTA_US q2@
   
BIG_DELTA_MIN q2@
 D<
IF
." Big delta is too small, min Big delta = "
BIG_DELTA_MIN q2@
   
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D/
   
1 noop
S>D
 D+
DROP
 .
."  ms ("
BIG_DELTA_MIN q2@
 D.
."  us)"
 CR
                                      XGOTO 0
THEN
THEN
[ 56832 ,code 180 ,code ] 15 far@
S>D
BIG_DELTA_US q2@
   
SM_DELTA_US q2@
 D-
   
DIFF_TRAMP @
   
TSEL180 @
 +
   
2 noop
   
TRAMP @
 [ 45207 ,code 48662 ,code ] swapdrop
 +
   
2 noop
   
[ 56832 ,code 12 ,code ] 15 far@
 [ 45207 ,code 48662 ,code ] swapdrop
 +
INTTOLONG
 D-
 D*
EXTRA_DELTA 2!
TEMPL1 q2@
SPACE_PRE 2!
TEMPL2 q2@
SPACE_POST 2!
EXTRA_DELTA q2@
   
 [ 56832 ,code 2 ,code 56832 ,code 0 ,code  ]
 D/
TEMPL3 2!
TEMPL3 q2@
   
SPACE_PRE q2@
 D> NOT
   
TEMPL3 q2@
   
SPACE_POST q2@
 D> NOT
 &&
IF
SPACE_PRE q2@
   
TEMPL3 q2@
 D-
EXTRA_TE_US 2!
SPACE_POST q2@
   
TEMPL3 q2@
 D-
EXTRA_TE2_US 2!
TEMPL3 q2@
EXTRA_DELTA_US 2!
TEMPL3 q2@
EXTRA_DELTA2_US 2!
 ELSE
MIN_TE q2@
   
2 noop
S>D
TEMPL3 q2@
 D*
 D+
MIN_TE 2!
." TE is too short to realise given diffusion timing"
 CR
." TE is too short, increase to "
MIN_TE q2@
   
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D/
   
1 noop
S>D
 D+
DROP
 .
."  ms (="
MIN_TE q2@
 D.
."  us)"
 CR
                                      XGOTO 0
THEN
[ 56832 ,code 182 ,code ] 15 far@
   
0 noop
 >
IF
EXTRA_DELTA_US q2@
   
3 noop
S>D
 D<
IF
." Increase TE and Big delta by "
3 noop
S>D
EXTRA_DELTA_US q2@
 D-
   
2 noop
S>D
 D*
 D.
."  us"
 CR
                                      XGOTO 0
THEN
EXTRA_DELTA2_US q2@
   
3 noop
S>D
 D<
IF
." Increase TE by "
3 noop
S>D
EXTRA_DELTA2_US q2@
 D-
 D.
."  us"
 CR
                                      XGOTO 0
THEN
THEN
 [ 56832 ,code 10 ,code 56832 ,code 0 ,code  ]
   
EXTRA_TE_US q2@
 D*
EXTRA_TE_US 2!
 [ 56832 ,code 10 ,code 56832 ,code 0 ,code  ]
   
EXTRA_TE2_US q2@
   
 [ 56832 ,code 35 ,code ]
S>D
 D-
 D*
EXTRA_TE2_US 2!
 [ 56832 ,code 10 ,code 56832 ,code 0 ,code  ]
   
EXTRA_DELTA_US q2@
 D*
EXTRA_DELTA_US 2!
 [ 56832 ,code 10 ,code 56832 ,code 0 ,code  ]
   
EXTRA_DELTA2_US q2@
 D*
EXTRA_DELTA2_US 2!
 [ 56832 ,code 5300 ,code ]
WAITTIMER
STARTTIMER
BIG_DELTA_US q2@
   
SM_DELTA_US q2@
   
 [ 56832 ,code 3 ,code 56832 ,code 0 ,code  ]
 D/
 D-
   
 [ 56832 ,code 500 ,code 56832 ,code 0 ,code  ]
 D+
   
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D/
   
 [ 56832 ,code 63 ,code 56832 ,code 0 ,code  ]
 D*
   
 [ 56832 ,code 5 ,code 56832 ,code 0 ,code  ]
 D+
   
 [ 56832 ,code 10 ,code 56832 ,code 0 ,code  ]
 D/
TEMPL1 2!
SM_DELTA_US q2@
   
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D/
TEMPL2 2!
TEMPL2 q2@
   
TEMPL2 q2@
 D*
TEMPL2 2!
 [ 56832 ,code 1 ,code 56832 ,code 0 ,code  ]
   
DIFF_READ @
S>D
 D*
   
0 noop
2* GRAD_VAR +
@
S>D
 D*
   
 [ 56832 ,code 32767 ,code 56832 ,code 0 ,code  ]
 D/
   
 [ 56832 ,code 1 ,code 56832 ,code 0 ,code  ]
   
DIFF_READ @
S>D
 D*
   
0 noop
2* GRAD_VAR +
@
S>D
 D*
   
 [ 56832 ,code 32767 ,code 56832 ,code 0 ,code  ]
 D/
 D*
TEMPL3 2!
TEMPL3 q2@
   
 [ 56832 ,code 1 ,code 56832 ,code 0 ,code  ]
   
DIFF_PHASE @
S>D
 D*
   
0 noop
2* GRAD_VAR +
@
S>D
 D*
   
 [ 56832 ,code 32767 ,code 56832 ,code 0 ,code  ]
 D/
   
 [ 56832 ,code 1 ,code 56832 ,code 0 ,code  ]
   
DIFF_PHASE @
S>D
 D*
   
0 noop
2* GRAD_VAR +
@
S>D
 D*
   
 [ 56832 ,code 32767 ,code 56832 ,code 0 ,code  ]
 D/
 D*
 D+
TEMPL3 2!
TEMPL3 q2@
   
 [ 56832 ,code 1 ,code 56832 ,code 0 ,code  ]
   
DIFF_SLICE @
S>D
 D*
   
0 noop
2* GRAD_VAR +
@
S>D
 D*
   
 [ 56832 ,code 32767 ,code 56832 ,code 0 ,code  ]
 D/
   
 [ 56832 ,code 1 ,code 56832 ,code 0 ,code  ]
   
DIFF_SLICE @
S>D
 D*
   
0 noop
2* GRAD_VAR +
@
S>D
 D*
   
 [ 56832 ,code 32767 ,code 56832 ,code 0 ,code  ]
 D/
 D*
 D+
   
 [ 56832 ,code 500 ,code 56832 ,code 0 ,code  ]
 D+
   
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D/
TEMPL3 2!
TEMPL3 q2@
   
 [ 56832 ,code 63 ,code 56832 ,code 0 ,code  ]
 D*
   
 [ 56832 ,code 10 ,code 56832 ,code 0 ,code  ]
 D/
TEMPL3 2!
TEMPL3 q2@
   
TEMPL2 q2@
 D*
   
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D/
   
TEMPL1 q2@
 D*
   
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D/
TEMPL4 2!
[ 56832 ,code 8 ,code ] 15 far@
   
1 noop
 =
   
[ 56832 ,code 180 ,code ] 15 far@
   
1 noop
 =
 &&
IF
 CR
." DW grad: X="
DIFF_READ @
 .
." , Y="
DIFF_PHASE @
 .
." , Z="
DIFF_SLICE @
 .
."  DAC"
 CR
 CR
." b-value ~ "
TEMPL4 q2@
 D.
."  (s/mm^2);"
 CR
." DW grad array for this b-value:"
 CR
."  X="
DIFF_DIR_CNT @
   
3 noop
 [ 45207 ,code 48662 ,code ] swapdrop
2* DIFF_GRAD_DIR +
@
S>D
 D.
." , Y="
DIFF_DIR_CNT @
   
3 noop
 [ 45207 ,code 48662 ,code ] swapdrop
   
1 noop
 +
2* DIFF_GRAD_DIR +
@
S>D
 D.
." , Z="
DIFF_DIR_CNT @
   
3 noop
 [ 45207 ,code 48662 ,code ] swapdrop
   
2 noop
 +
2* DIFF_GRAD_DIR +
@
S>D
 D.
." ,"
 CR
THEN
 [ 56832 ,code 19700 ,code ]
WAITTIMER
STARTTIMER
TSEL90 @
   
[ 56832 ,code 12 ,code ] 15 far@
 +
   
TREF @
 +
   
4 noop
   
TRAMP @
 [ 45207 ,code 48662 ,code ] swapdrop
 +
S>D
TE_A 2!
FLOW_COMP_ON @
   
TSEL90 @
   
2 noop
 /
   
2 noop
   
TRAMP @
 [ 45207 ,code 48662 ,code ] swapdrop
 +
 [ 45207 ,code 48662 ,code ] swapdrop
T_FLOW !
TE_A q2@
   
T_FLOW @
S>D
 D+
TE_A 2!
TSEL90 @
   
2 noop
 /
   
[ 56832 ,code 12 ,code ] 15 far@
 +
   
TDP @
 +
   
4 noop
   
TRAMP @
 [ 45207 ,code 48662 ,code ] swapdrop
 +
S>D
TACQ_2 q2@
 D+
TE_B 2!
TE_A q2@
DROP
TEMP !
TE_B q2@
   
TEMP @
S>D
 D>
IF
TE_B q2@
DROP
TEMP !
THEN
[ 56832 ,code 180 ,code ] 15 far@
   
1 noop
 =
   
[ 56832 ,code 182 ,code ] 15 far@
   
1 noop
 =
 &&
IF
MIN_TE q2@
   
EXTRA_DELTA q2@
 D+
   
 [ 56832 ,code 1000 ,code ]
S>D
 D+
MIN_TE 2!
 ELSE
[ 56832 ,code 180 ,code ] 15 far@
   
1 noop
 =
   
DIFF_READ @
   
0 noop
 =
 &&
   
DIFF_PHASE @
   
0 noop
 =
 &&
   
DIFF_SLICE @
   
0 noop
 =
 &&
IF
MIN_TE q2@
   
EXTRA_DELTA q2@
 D+
   
2 noop
S>D
SM_DELTA_US q2@
 D*
 D+
   
2 noop
   
TRAMP @
 [ 45207 ,code 48662 ,code ] swapdrop
S>D
 D+
   
 [ 56832 ,code 1000 ,code ]
S>D
 D+
MIN_TE 2!
THEN
THEN
[ 56832 ,code 8 ,code ] 15 far@
   
1 noop
 =
IF
[ 56832 ,code 180 ,code ] 15 far@
   
0 noop
 =
IF
 CR
." Minimum TE = "
TEMP @
   
21 noop
 +
   
 [ 56832 ,code 500 ,code ]
 /
   
1 noop
 +
 .
."  ms ("
2 noop
   
TEMP @
   
21 noop
 +
 [ 45207 ,code 48662 ,code ] swapdrop
 .
."  us)"
 CR
 ELSE
 CR
." Minimum TE = "
MIN_TE q2@
 D.
."  us"
 CR
THEN
TE_B q2@
DROP
TEMP !
TE_A q2@
   
TE_B q2@
 D>
IF
TE_A q2@
DROP
TEMP !
THEN
." Minimum esp = "
TEMP @
   
21 noop
 +
   
 [ 56832 ,code 500 ,code ]
 /
   
1 noop
 +
 .
."  ms ("
2 noop
   
TEMP @
   
21 noop
 +
 [ 45207 ,code 48662 ,code ] swapdrop
 .
."  us)"
 CR
THEN
[ 56832 ,code 4 ,code ] 15 far@
S>D
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D*
   
MIN_TE q2@
 D<
IF
 CR
."  Echo time should be greater than Minimum TE (= "
MIN_TE q2@
 D.
."  us)"
 CR
                                      XGOTO 0
THEN
[ 56832 ,code 180 ,code ] 15 far@
IF
[ 56832 ,code 4 ,code ] 15 far@
INTTOLONG
   
 [ 56832 ,code 500 ,code 56832 ,code 0 ,code  ]
 D*
TEMPL1 2!
 ELSE
[ 56832 ,code 80 ,code ] 15 far@
INTTOLONG
   
 [ 56832 ,code 500 ,code 56832 ,code 0 ,code  ]
 D*
TEMPL1 2!
THEN
TEMPL1 q2@
   
TE_A q2@
   
21 noop
S>D
 D+
DROP
INTTOLONG
 D-
   
0 noop
S>D
 D<
   
TEMPL1 q2@
   
TE_B q2@
   
21 noop
S>D
 D+
DROP
INTTOLONG
 D-
   
0 noop
S>D
 D<
 ||
IF
." TE is too short, increase to "
TEMP @
   
21 noop
 +
   
 [ 56832 ,code 500 ,code ]
 /
   
1 noop
 +
 .
."  ms"
 CR
                                      XGOTO 0
THEN
TEMPL1 q2@
   
TE_B q2@
DROP
INTTOLONG
 D-
TE_BALANCE_BL 2!
TEMPL1 q2@
   
TE_A q2@
DROP
INTTOLONG
 D-
TE_BALANCE_AL 2!
DIXON_ON @
IF
TE_BALANCE_BL q2@
   
DELTA_2 @
INTTOLONG
 D+
TE_BALANCE_BL 2!
TE_BALANCE_AL q2@
   
DELTA_2 @
INTTOLONG
 D-
TE_BALANCE_AL 2!
THEN
TE_BALANCE_BL q2@
   
 [ 56832 ,code 10 ,code 56832 ,code 0 ,code  ]
 D*
   
 [ 56832 ,code 210 ,code 56832 ,code 0 ,code  ]
 D-
TE_BALANCE_BL_TEMP1 2!
TRAMP @
   
3 noop
 [ 45207 ,code 48662 ,code ] swapdrop
   
TDP @
 +
   
TFILTER @
 -
   
[ 56832 ,code 130 ,code ] 15 far@
 -
   
21 noop
 -
   
16 noop
 -
INTTOLONG
TE_BALANCE_BL_TEMP2 2!
[ 56832 ,code 80 ,code ] 15 far@
INTTOLONG
   
 [ 56832 ,code 500 ,code 56832 ,code 0 ,code  ]
 D*
   
TE_B q2@
DROP
INTTOLONG
 D-
TE_BALANCE_BL_ESP 2!
TE_BALANCE_BL_ESP q2@
   
 [ 56832 ,code 10 ,code 56832 ,code 0 ,code  ]
 D*
   
 [ 56832 ,code 210 ,code 56832 ,code 0 ,code  ]
 D-
TE_BALANCE_BL_TEMP1_ESP 2!
[ 56832 ,code 180 ,code ] 15 far@
   
[ 56832 ,code 80 ,code ] 15 far@
INTTOLONG
   
 [ 56832 ,code 500 ,code 56832 ,code 0 ,code  ]
 D*
   
TE_B q2@
   
21 noop
S>D
 D+
DROP
INTTOLONG
 D-
   
0 noop
S>D
 D<
   
[ 56832 ,code 80 ,code ] 15 far@
INTTOLONG
   
 [ 56832 ,code 500 ,code 56832 ,code 0 ,code  ]
 D*
   
TE_A q2@
   
21 noop
S>D
 D+
DROP
INTTOLONG
 D-
   
0 noop
S>D
 D<
 ||
 &&
IF
TE_B q2@
DROP
TEMP !
TE_A q2@
   
TE_B q2@
 D>
IF
TE_A q2@
DROP
TEMP !
THEN
." esp too short: increase esp to at least "
TEMP @
   
21 noop
 +
   
 [ 56832 ,code 500 ,code ]
 /
   
1 noop
 +
 .
."  ms"
 CR
                                      XGOTO 0
THEN
SLICE_FREQ_LONG q2@
   
SLICE_FREQ_VAR q2@
DROP
INTTOLONG
 D+
TEMPL1 2!
READ_FREQ_LONG q2@
 QDNEGATE
   
[ 56832 ,code 32 ,code ] 15 far@
INTTOLONG
 D-
TEMPL2 2!
TEMPL1 q2@
   
0 noop
S>D
 D>
IF
[ 56832 ,code 90 ,code ] 15 far@
[ 56832 ,code 88 ,code ] 15 far!
 ELSE
[ 56832 ,code 92 ,code ] 15 far@
[ 56832 ,code 88 ,code ] 15 far!
THEN
OVERHEAD @
INTTOLONG
   
TACQ q2@
   
TRAMP @
INTTOLONG
 D+
   
 [ 56832 ,code 16 ,code 56832 ,code 0 ,code  ]
 D*
   
 [ 56832 ,code 10 ,code 56832 ,code 0 ,code  ]
 D/
 D+
TEMPL3 2!
TEMPL1 q2@
   
TEMPL2 q2@
 D+
   
TEMPL3 q2@
 D*
TEMPL4 2!
[ 56832 ,code 88 ,code ] 15 far@
INTTOLONG
   
TEMPL1 q2@
 D*
   
[ 56832 ,code 94 ,code ] 15 far@
INTTOLONG
   
TEMPL2 q2@
 D*
 D+
TEMPL5 2!
 [ 56832 ,code 16 ,code 56832 ,code 0 ,code  ]
   
TEMPL5 q2@
 D*
   
 [ 56832 ,code 10 ,code 56832 ,code 0 ,code  ]
 D/
TEMPL5 2!
TEMPL4 q2@
   
TEMPL5 q2@
 D+
TEMPL4 2!
TEMPL4 q2@
   
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D/
TEMPL5 2!
TEMPL5 q2@
   
DEG_360 @
INTTOLONG
 D/REM
PHASE_ANG 2!
TEMPL4 q2@
   
TEMPL5 q2@
   
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D*
 D-
TEMPL5 2!
TEMPL5 q2@
DROP
REMAINDER_PHASE !
0 noop
PHASE_CORRECTION !
VIEWS_PER_SEG @
   
[ 56832 ,code 108 ,code ] 15 far@
 +
INTTOLONG
   
[ 56832 ,code 80 ,code ] 15 far@
INTTOLONG
 D*
   
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D*
TEMPL1 2!
FLOW_COMP_ON @
IF
TEMPL1 q2@
   
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D+
TEMPL1 2!
THEN
TEMPL1 q2@
   
TRAMP @
   
TSEL90 @
   
2 noop
 /
 +
INTTOLONG
 D+
TEMPL1 2!
TEMPL1 q2@
   
3 noop
   
TRAMP @
 [ 45207 ,code 48662 ,code ] swapdrop
   
[ 56832 ,code 78 ,code ] 15 far@
 +
INTTOLONG
 D+
   
TACQ_2 q2@
 D+
   
26 noop
S>D
 D+
TEMPL1 2!
TRAMP @
   
 [ 56832 ,code 130 ,code ]
 <
IF
TEMPL1 q2@
   
17 noop
S>D
 D+
TEMPL1 2!
THEN
TRAMP @
   
 [ 56832 ,code 120 ,code ]
 <
IF
TEMPL1 q2@
   
30 noop
S>D
 D+
TEMPL1 2!
THEN
TRAMP @
   
 [ 56832 ,code 110 ,code ]
 <
IF
TEMPL1 q2@
   
30 noop
S>D
 D+
TEMPL1 2!
THEN
TEMPL1 q2@
   
 [ 56832 ,code 10200 ,code 56832 ,code 0 ,code  ]
 D+
   
 [ 56832 ,code 70 ,code 56832 ,code 0 ,code  ]
 D+
   
 [ 56832 ,code 69 ,code 56832 ,code 0 ,code  ]
 D+
TEMPL1 2!
[ 56832 ,code 124 ,code ] 15 far@
IF
30 noop
   
2 noop
   
TRAMP @
 [ 45207 ,code 48662 ,code ] swapdrop
 +
   
[ 56832 ,code 116 ,code ] 15 far@
 +
S>D
TEMPL2 2!
[ 56832 ,code 126 ,code ] 15 far@
IF
TEMPL2 q2@
   
 [ 56832 ,code 1000 ,code ]
   
T_CHESS_GAUSS @
 [ 45207 ,code 48662 ,code ] swapdrop
S>D
 D+
TEMPL2 2!
 ELSE
TEMPL2 q2@
   
[ 56832 ,code 118 ,code ] 15 far@
S>D
 D+
TEMPL2 2!
THEN
 ELSE
0 noop
S>D
TEMPL2 2!
THEN
0 noop
INTTOLONG
   
10 noop
S>D
 D/
TEMPL3 2!
DE_ON @
IF
TEMPL3 q2@
   
[ 56832 ,code 80 ,code ] 15 far@
INTTOLONG
   
 [ 56832 ,code 500 ,code 56832 ,code 0 ,code  ]
 D*
 D+
   
[ 56832 ,code 12 ,code ] 15 far@
S>D
 D+
   
2 noop
   
TRAMP @
 [ 45207 ,code 48662 ,code ] swapdrop
S>D
 D+
   
TSEL180 @
   
TSEL90 @
 +
   
2 noop
 /
S>D
 D+
   
21 noop
S>D
 D+
   
 [ 56832 ,code 32 ,code ]
S>D
 D+
   
TE_BALANCE_BL q2@
 D+
TEMPL3 2!
THEN
[ 56832 ,code 96 ,code ] 15 far@
IF
TEMPL3 q2@
   
2 noop
   
TRAMP @
 [ 45207 ,code 48662 ,code ] swapdrop
   
[ 56832 ,code 98 ,code ] 15 far@
 +
   
 [ 56832 ,code 240 ,code ]
 +
S>D
 D+
TEMPL3 2!
THEN
TEMPL1 q2@
   
TEMPL2 q2@
 D+
   
TEMPL3 q2@
 D+
TR_MIN 2!
[ 56832 ,code 40 ,code ] 15 far@
   
TSEL_SAT @
 +
   
3 noop
   
TRAMP @
 [ 45207 ,code 48662 ,code ] swapdrop
 +
   
 [ 56832 ,code 520 ,code ]
 +
   
[ 56832 ,code 84 ,code ] 15 far@
 +
INTTOLONG
TEMPL1 2!
NO_PB @
   
[ 56832 ,code 82 ,code ] 15 far@
 [ 45207 ,code 48662 ,code ] swapdrop
INTTOLONG
   
TEMPL1 q2@
 D*
TEMPL1 2!
TR_MIN q2@
   
TEMPL1 q2@
 D+
TR_MIN 2!
[ 56832 ,code 180 ,code ] 15 far@
IF
TRAMP @
   
[ 56832 ,code 78 ,code ] 15 far@
 +
   
VIEWS_PER_SEG @
 [ 45207 ,code 48662 ,code ] swapdrop
S>D
TEMPL1 2!
TSEL180 @
S>D
TACQ q2@
 D+
   
2 noop
   
[ 56832 ,code 12 ,code ] 15 far@
 [ 45207 ,code 48662 ,code ] swapdrop
S>D
 D+
   
8 noop
   
TRAMP @
 [ 45207 ,code 48662 ,code ] swapdrop
S>D
 D+
   
2 noop
   
[ 56832 ,code 78 ,code ] 15 far@
 [ 45207 ,code 48662 ,code ] swapdrop
S>D
 D+
T_SEGMENT 2!
[ 56832 ,code 4 ,code ] 15 far@
S>D
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D*
   
TACQ_2 q2@
 D+
   
5 noop
   
TRAMP @
 [ 45207 ,code 48662 ,code ] swapdrop
S>D
 D+
   
[ 56832 ,code 78 ,code ] 15 far@
S>D
 D+
   
[ 56832 ,code 98 ,code ] 15 far@
S>D
 D+
TR_MIN 2!
TR_MIN q2@
   
T_SEGMENT q2@
   
VIEWS_PER_SEG @
   
1 noop
 -
S>D
 D*
 D+
TR_MIN 2!
TR_MIN q2@
   
TEMPL1 q2@
 D+
TR_MIN 2!
THEN
[ 56832 ,code 162 ,code ] 15 far@
S>D
TSELMTCL q2@
 D*
   
[ 56832 ,code 162 ,code ] 15 far@
   
1 noop
 -
S>D
[ 56832 ,code 164 ,code ] 15 far@
INTTOLONG
 D*
   
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D*
 D+
   
[ 56832 ,code 172 ,code ] 15 far@
   
2 noop
   
TRAMP @
 [ 45207 ,code 48662 ,code ] swapdrop
 +
INTTOLONG
 D+
   
[ 56832 ,code 166 ,code ] 15 far@
INTTOLONG
   
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D*
 D+
TEMPL1 2!
[ 56832 ,code 160 ,code ] 15 far@
IF
TR_MIN q2@
   
TEMPL1 q2@
 D+
TR_MIN 2!
2 noop
   
TRAMP @
 [ 45207 ,code 48662 ,code ] swapdrop
   
[ 56832 ,code 172 ,code ] 15 far@
 +
   
 [ 56832 ,code 100 ,code ]
 +
INTER_CEST_CAL_MIN !
[ 56832 ,code 164 ,code ] 15 far@
S>D
INTER_CEST_CAL_MIN @
S>D
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D/
 D-
DROP
INTER_CEST_CAL !
INTER_CEST_CAL @
   
1 noop
 <
IF
." Inter-CEST delay too short, extend by "
INTER_CEST_CAL @
 0-
   
1 noop
 +
 .
."  ms"
 CR
."  "
                                      XGOTO 0
THEN
THEN
[ 56832 ,code 2 ,code ] 15 far@
   
0 noop
 =
IF
TR_MIN q2@
   
BATCH_SLICES @
S>D
 D*
   
 [ 56832 ,code 1000 ,code ]
S>D
 D/
   
1 noop
S>D
 D+
DROP
[ 56832 ,code 2 ,code ] 15 far!
THEN
T_RESP_PLATEAU @
   
0 noop
 =
IF
[ 56832 ,code 2 ,code ] 15 far@
T_RESP_PLATEAU !
THEN
TR_MIN q2@
   
BATCH_SLICES @
INTTOLONG
 D*
TEMPL1 2!
TEMPL1 q2@
   
 [ 56832 ,code 1000 ,code ]
S>D
 D/
   
1 noop
S>D
 D+
DROP
TEMP !
[ 56832 ,code 34 ,code ] 15 far@
   
T_RESP_PLATEAU @
   
TEMP @
 <
 &&
   
[ 56832 ,code 146 ,code ] 15 far@
   
0 noop
 =
 &&
IF
." Gate interval ("
T_RESP_PLATEAU @
 .
." ms) is shorter than min TR ("
TEMP @
 .
." ms)"
 CR
1 noop
[ 56832 ,code 146 ,code ] 15 far!
THEN
[ 56832 ,code 8 ,code ] 15 far@
   
1 noop
 =
   
[ 56832 ,code 34 ,code ] 15 far@
   
0 noop
 !=
 &&
IF
." Resp plateau set to "
T_RESP_PLATEAU @
 .
."  ms"
 CR
THEN
[ 56832 ,code 8 ,code ] 15 far@
   
1 noop
 =
IF
." Minimum TR = "
TEMP @
 .
."  ms"
 CR
THEN
[ 56832 ,code 2 ,code ] 15 far@
S>D
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D*
   
BATCH_SLICES @
S>D
 D/
   
TR_MIN q2@
 D-
TR_EXTEND_US 2!
TR_EXTEND_US q2@
   
0 noop
S>D
 D<
IF
." TR too short, increase to "
TEMP @
 .
."  ms"
 CR
."  "
BATCH_SLICES @
   
1 noop
 >
IF
." , or decrease number of slices (batch) to "
[ 56832 ,code 2 ,code ] 15 far@
   
1 noop
 -
S>D
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D*
   
TR_MIN q2@
 D/
DROP
 .
 CR
THEN
                                      XGOTO 0
THEN
[ 56832 ,code 180 ,code ] 15 far@
IF
[ 56832 ,code 2 ,code ] 15 far@
S>D
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D*
   
BATCH_SLICES @
S>D
 D/
   
TR_MIN q2@
 D-
TR_EXTEND_US 2!
THEN
TR_EXTEND_US q2@
   
 [ 56832 ,code 10 ,code 56832 ,code 0 ,code  ]
 D*
TR_EXTEND_USL 2!
TR_MIN q2@
   
 [ 56832 ,code 1000 ,code ]
S>D
 D/
TR_MIN 2!
T_RESP_PLATEAU @
S>D
TR_MIN q2@
 D/
DROP
TEMP !
TEMP @
[ 56832 ,code 110 ,code ] 15 far!
[ 56832 ,code 110 ,code ] 15 far@
   
BATCH_SLICES @
 >
IF
BATCH_SLICES @
[ 56832 ,code 110 ,code ] 15 far!
THEN
T_RESP_PLATEAU @
   
[ 56832 ,code 2 ,code ] 15 far@
 /
TEMP !
TEMP @
NO_VIEWS_PER_GATING_INTERVAL !
NO_VIEWS_PER_GATING_INTERVAL @
   
0 noop
 =
IF
NO_VIEWS @
   
VIEWS_PER_SEG @
 /
NO_VIEWS_PER_GATING_INTERVAL !
THEN
[ 56832 ,code 8 ,code ] 15 far@
   
1 noop
 =
   
[ 56832 ,code 34 ,code ] 15 far@
   
0 noop
 !=
 &&
IF
." Slices per gate interval = "
[ 56832 ,code 110 ,code ] 15 far@
 .
 CR
." Views per gate interval = "
NO_VIEWS_PER_GATING_INTERVAL @
 .
 CR
THEN
GS_COMP @
S>D
TEMPL1 2!
TEMPL1 q2@
   
TEMPL1 q2@
   
[ 56832 ,code 50 ,code ] 15 far@
   
[ 56832 ,code 66 ,code ] 15 far@
 +
S>D
 D*
   
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D/
 D+
TEMPL1 2!
TEMPL1 q2@
   
[ 56832 ,code 72 ,code ] 15 far@
INTTOLONG
 D*
   
 [ 56832 ,code 100 ,code 56832 ,code 0 ,code  ]
 D/
TEMPL2 2!
TEMPL1 q2@
   
TEMPL2 q2@
 D-
TEMPL3 2!
TEMPL2 q2@
   
DACMAXLONG q2@
 D+
   
0 noop
S>D
 D<
   
TEMPL3 q2@
   
DACMAXLONG q2@
 D+
   
0 noop
S>D
 D<
 OR
IF
." Reduce slice grad comp"
 CR
                                      XGOTO 0
THEN
TEMPL3 q2@
DROP
GS_RP !
TEMPL2 q2@
   
TREF @
   
TRAMP @
 +
INTTOLONG
 D*
   
TDP @
   
TRAMP @
 +
INTTOLONG
 D/
DROP
GSP_RP !
GP_SL_ON @
   
0 noop
 >
   
NO_VIEWS_2 @
   
1 noop
 >
 &&
IF
GP_SL_INIT_VAR @
S>D
TEMPL2 2!
TEMPL1 q2@
   
TEMPL2 q2@
 D+
TEMPL1 2!
TEMPL1 q2@
   
 [ 56832 ,code -32767 ,code 56832 ,code -1 ,code  ]
 D<
IF
." FOV in slice direction too small"
 CR
                                      XGOTO 0
THEN
THEN
GR_COMP @
S>D
TEMPL1 2!
TEMPL1 q2@
   
TEMPL1 q2@
   
[ 56832 ,code 48 ,code ] 15 far@
INTTOLONG
 D*
   
8 noop
S>D
 D/
   
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D/
 D+
TEMPL1 2!
TEMPL1 q2@
   
[ 56832 ,code 70 ,code ] 15 far@
S>D
 D*
   
 [ 56832 ,code 100 ,code 56832 ,code 0 ,code  ]
 D/
TEMPL2 2!
TEMPL1 q2@
   
TEMPL2 q2@
 D-
TEMPL3 2!
TEMPL2 q2@
   
DACMAXLONG q2@
 D+
   
0 noop
S>D
 D<
   
TEMPL3 q2@
   
DACMAXLONG q2@
 D+
   
0 noop
S>D
 D<
 OR
IF
." Reduce read grad comp"
 CR
                                      XGOTO 0
THEN
TEMPL3 q2@
DROP
GR_DP !
TEMPL2 q2@
   
TDP @
   
TRAMP @
 +
INTTOLONG
 D*
 QDNEGATE
   
TREF @
   
TRAMP @
 +
INTTOLONG
 D/
DROP
GRP_DP !
0 noop
GRP_DP_1 !
FLOW_COMP_ON @
IF
GR_COMP_FLOW @
S>D
TEMPL1 2!
TEMPL1 q2@
   
TEMPL1 q2@
   
[ 56832 ,code 48 ,code ] 15 far@
INTTOLONG
 D*
   
8 noop
S>D
 D/
   
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D/
 D+
TEMPL1 2!
TEMPL1 q2@
   
[ 56832 ,code 70 ,code ] 15 far@
S>D
 D*
   
 [ 56832 ,code 100 ,code 56832 ,code 0 ,code  ]
 D/
TEMPL2 2!
TEMPL1 q2@
   
TEMPL2 q2@
 D-
TEMPL3 2!
TEMPL2 q2@
   
DACMAXLONG q2@
 D+
   
0 noop
S>D
 D<
   
TEMPL3 q2@
   
DACMAXLONG q2@
 D+
   
0 noop
S>D
 D<
 OR
IF
." Flow comp grad amp caused overflow"
 CR
                                      XGOTO 0
THEN
TEMPL2 q2@
   
TDP @
   
TRAMP @
 +
INTTOLONG
 D*
 QDNEGATE
   
TREF @
   
TRAMP @
 +
INTTOLONG
 D/
DROP
GRP_DP_1 !
GR_VAR @
S>D
TEMPL3 2!
GR_UNDERSAMPLE @
S>D
TEMPL4 2!
GR_OVERSAMPLE @
S>D
TEMPL5 2!
TEMPL3 q2@
   
TEMPL4 q2@
 D*
   
TEMPL5 q2@
 D/
TEMPL3 2!
TEMPL3 q2@
   
TEMPL3 q2@
   
[ 56832 ,code 48 ,code ] 15 far@
INTTOLONG
 D*
   
 [ 56832 ,code 8000 ,code 56832 ,code 0 ,code  ]
 D/
 D+
TEMPL3 2!
TEMPL3 q2@
   
[ 56832 ,code 70 ,code ] 15 far@
S>D
 D*
   
 [ 56832 ,code 100 ,code 56832 ,code 0 ,code  ]
 D/
TEMPL3 2!
TEMPL3 q2@
DROP
GR_FLOW !
GR_FLOW @
S>D
DACMAXLONG q2@
 D+
   
0 noop
S>D
 D<
IF
." Flow comp grad amp caused overflow"
 CR
                                      XGOTO 0
THEN
GR_FLOW @
 0-
GRP_DP !
THEN
[ 56832 ,code 138 ,code ] 15 far@
   
1 noop
 =
IF
NO_VIEWS @
   
VIEWS_PER_SEG @
 /
INTTOLONG
   
NO_VIEWS_2 @
INTTOLONG
 D*
   
[ 56832 ,code 140 ,code ] 15 far@
INTTOLONG
 D+
TEMPL1 2!
TEMPL1 q2@
   
NO_SLICES @
   
BATCH_SLICES @
 /
INTTOLONG
 D*
   
NO_AVERAGES @
INTTOLONG
 D*
TEMPL1 2!
." Duration="
[ 56832 ,code 2 ,code ] 15 far@
S>D
TEMPL1 q2@
 D*
   
NO_EXPERIMENTS @
S>D
 D*
 D.
 CR
                                      XGOTO 0
THEN
FLOW_COMP_ON @
IF
 [ 56832 ,code -28036 ,code 56832 ,code 0 ,code  ]
TEMPL1 2!
 ELSE
 [ 56832 ,code 27500 ,code ]
S>D
TEMPL1 2!
THEN
TEMPL1 q2@
DROP
WAITTIMER
STARTTIMER
GRP_DP @
G1 !
GRP_DP_1 @
G2 !
1 noop
MR3040_SELECTMATRIX
23 noop
[ 56832 ,code 56 ,code ] 15 far@
   
GS_VAR_RESCALE @
 [ 45207 ,code 48662 ,code ] swapdrop
0 noop
[ 56832 ,code 52 ,code ] 15 far@
   
G2 @
 [ 45207 ,code 48662 ,code ] swapdrop
CREATEMATRIXTEST
IF
                                      XGOTO 0
THEN
[ 56832 ,code 99 ,code ] us
 [ 56832 ,code 279 ,code ]
[ 56832 ,code 56 ,code ] 15 far@
   
GS_RP @
 [ 45207 ,code 48662 ,code ] swapdrop
0 noop
[ 56832 ,code 52 ,code ] 15 far@
   
G1 @
 [ 45207 ,code 48662 ,code ] swapdrop
CREATEMATRIXTEST
IF
                                      XGOTO 0
THEN
[ 56832 ,code 99 ,code ] us
21 noop
[ 56832 ,code 56 ,code ] 15 far@
   
GS_VAR_RESCALE @
 [ 45207 ,code 48662 ,code ] swapdrop
0 noop
0 noop
CREATEMATRIXTEST
IF
                                      XGOTO 0
THEN
[ 56832 ,code 99 ,code ] us
 [ 56832 ,code 277 ,code ]
0 noop
0 noop
0 noop
CREATEMATRIXTEST
IF
                                      XGOTO 0
THEN
[ 56832 ,code 99 ,code ] us
 [ 56832 ,code 60 ,code ]
DIFF_SLICE @
 0-
DIFF_PHASE @
 0-
DIFF_READ @
 0-
CREATEMATRIXTEST
IF
                                      XGOTO 0
THEN
[ 56832 ,code 99 ,code ] us
 [ 56832 ,code 280 ,code ]
[ 56832 ,code 82 ,code ] 15 far@
   
[ 56832 ,code 42 ,code ] 15 far@
 [ 45207 ,code 48662 ,code ] swapdrop
[ 56832 ,code 82 ,code ] 15 far@
   
[ 56832 ,code 42 ,code ] 15 far@
 [ 45207 ,code 48662 ,code ] swapdrop
[ 56832 ,code 82 ,code ] 15 far@
   
[ 56832 ,code 42 ,code ] 15 far@
 [ 45207 ,code 48662 ,code ] swapdrop
CREATEMATRIXTEST
IF
                                      XGOTO 0
THEN
[ 56832 ,code 99 ,code ] us
6 noop
[ 56832 ,code 120 ,code ] 15 far@
 0-
0 noop
0 noop
CREATEMATRIXTEST
IF
                                      XGOTO 0
THEN
[ 56832 ,code 99 ,code ] us
25 noop
[ 56832 ,code 160 ,code ] 15 far@
 0-
   
[ 56832 ,code 174 ,code ] 15 far@
 [ 45207 ,code 48662 ,code ] swapdrop
[ 56832 ,code 160 ,code ] 15 far@
 0-
   
[ 56832 ,code 174 ,code ] 15 far@
 [ 45207 ,code 48662 ,code ] swapdrop
[ 56832 ,code 160 ,code ] 15 far@
 0-
   
[ 56832 ,code 174 ,code ] 15 far@
 [ 45207 ,code 48662 ,code ] swapdrop
CREATEMATRIXTEST
IF
                                      XGOTO 0
THEN
[ 56832 ,code 99 ,code ] us
0 noop
[ 56832 ,code 14 ,code ] 15 far!
[ 56832 ,code 0 ,code ] 15 far@
   
0 noop
 >
IF
4 noop
[ 56832 ,code 14 ,code ] 15 far!
THEN
HOSTREQUEST
TIME !
TIME @
   
1 noop
 =
IF
0 noop
TIME !
THEN
 [ 56832 ,code 18500 ,code ]
WAITTIMER
RESYNC
CURRENT_SLICE @
   
1 noop
 -
   
[ 56832 ,code 110 ,code ] 15 far@
 n/rem
   
0 noop
 =
GATING_CONDITION_1 !
[ 56832 ,code 34 ,code ] 15 far@
IF
[ 56832 ,code 114 ,code ] 15 far@
   
1 noop
 =
IF
GATING_CONDITION_1 @
GATING_CONDITION !
 ELSE
[ 56832 ,code 114 ,code ] 15 far@
   
2 noop
 =
IF
GATING_CONDITION_1 @
GATING_CONDITION !
 ELSE
 [ 56832 ,code -1 ,code ]
GATING_CONDITION !
THEN
THEN
GATING_CONDITION @
IF
BEGIN
NOOP
HOSTREQUEST
drop
[ 56832 ,code 1 ,code ] 24G@SWAPAND
   
0 noop
 !=
 UNTIL
THEN
THEN
0 noop
ECHO_CNT !
0 noop
TOTAL_ECHO_CNT !
RESYNC
PHASE_90 @
PHASE
CLOCK @
MR3040_CLOCK
[ 56832 ,code 160 ,code ] 15 far@
IF
0 noop
CEST_COUNT !
LABEL 28
MTC_LIST @
 [ 56832 ,code 546 ,code ]
MR3040_SETLIST
25 noop
MR3040_SELECTMATRIX
5 noop
FREQUENCY_BUFFER
RESET_FREQUENCY
[ 56832 ,code 152 ,code ] 15 far@
   
0 noop
 >
IF
[ 56832 ,code 154 ,code ] 15 far@
USEROUT
THEN
MTC_GAUSSIAN @
IF
 [ 56832 ,code 100 ,code ]
   
22 noop
   
WARMUP @
 +
 -
TEMP_MAC !
TEMP_MAC @
 2- us 0.7us
[ 56832 ,code 178 ,code ] 15 far@
0 noop
MTC_RFNUM @
2* RBD +
@
SET_BOARD_MULTIPLIERS
MTC_RFNUM @
2* RAD +
@
MTC_RFNUM @
2* RBD +
@
   
4 noop
 +
SET3031ADDRESS
MTC_RFNUM @
2* RWT +
@
MTC_RFNUM @
2* RBD +
@
   
4 noop
 +
SET3031WAITS
MTC_RFNUM @
2* RBD +
@
   
4 noop
 +
APPEND_BOARDS_READY
0 noop
RFAMPON
WARMUP @
 2- us 0.7us
[ 56832 ,code 14 ,code ] 15 far@
RFON
MR3031_GO
[ 56832 ,code 170 ,code ] 15 far@
ms
0 noop
RFON
 ELSE
0 noop
0 noop
 [ 56832 ,code -232 ,code ]
Set_board_Multipliers
[ 56832 ,code 178 ,code ] 15 far@
0 noop
 [ 56832 ,code -240 ,code ]
Set_board_Multipliers
0 noop
20 noop
 [ 56832 ,code -236 ,code ]
 [ 56832 ,code -228 ,code ]
Set_addr_and_waits
 [ 56832 ,code -236 ,code ]
Append_Boards_Ready
 [ 56832 ,code -228 ,code ]
Append_Boards_Ready
0 noop
RFAMPON
WARMUP @
 2- us 0.7us
[ 56832 ,code 14 ,code ] 15 far@
RFON
MR3031_GO
[ 56832 ,code 170 ,code ] 15 far@
ms
RFOFF
0 noop
0 noop
 [ 56832 ,code -232 ,code ]
Set_board_Multipliers
0 noop
0 noop
 [ 56832 ,code -240 ,code ]
Set_board_Multipliers
8 noop
20 noop
 [ 56832 ,code -236 ,code ]
 [ 56832 ,code -228 ,code ]
Set_addr_and_waits
 [ 56832 ,code -236 ,code ]
Append_Boards_Ready
 [ 56832 ,code -228 ,code ]
Append_Boards_Ready
MR3031_GO
THEN
[ 56832 ,code 99 ,code ] us
[ 56832 ,code 152 ,code ] 15 far@
   
0 noop
 >
IF
[ 56832 ,code 156 ,code ] 15 far@
USEROUT
THEN
CLOCK @
MR3040_CLOCK
TRAMP @
 2- us 0.7us
[ 56832 ,code 172 ,code ] 15 far@
3- us 0.9us
STARTTIMER
TRAMP @
   
10 noop
 [ 45207 ,code 48662 ,code ] swapdrop
RET !
0 noop
FREQUENCY_BUFFER
RESET_FREQUENCY
CEST_COUNT @
   
1 noop
 +
CEST_COUNT !
RET @
WAITTIMER
CEST_COUNT @
   
[ 56832 ,code 162 ,code ] 15 far@
 <
IF
INTER_CEST_CAL @
0.8us ms
XGOTO 28
THEN
[ 56832 ,code 166 ,code ] 15 far@
   
0 noop
 >
IF
[ 56832 ,code 166 ,code ] 15 far@
ms
THEN
THEN
[ 56832 ,code 82 ,code ] 15 far@
   
NO_PB @
   
0 noop
 >
 &&
IF
0 noop
PB_INDEX !
BEGIN
PB_INDEX @
2* PB_ON +
@
   
1 noop
 =
IF
STARTTIMER
PB_INDEX @
2* PB_CHANNEL +
@
SAT_CHANNEL !
PB_INDEX @
2* PB_GS_SAT +
@
GS_SAT !
SAT_CHANNEL @
   
 [ 56832 ,code 512 ,code ]
 =
 0-
0 noop
2* SAT_ON_AR +
!
SAT_CHANNEL @
   
 [ 56832 ,code 32 ,code ]
 =
 0-
1 noop
2* SAT_ON_AR +
!
SAT_CHANNEL @
   
2 noop
 =
 0-
2 noop
2* SAT_ON_AR +
!
24 noop
0 noop
2* SAT_ON_AR +
@
   
GS_SAT @
 [ 45207 ,code 48662 ,code ] swapdrop
1 noop
2* SAT_ON_AR +
@
   
GS_SAT @
 [ 45207 ,code 48662 ,code ] swapdrop
2 noop
2* SAT_ON_AR +
@
   
GS_SAT @
 [ 45207 ,code 48662 ,code ] swapdrop
CREATEMATRIXTEST
IF
                                      XGOTO 0
THEN
[ 56832 ,code 99 ,code ] us
SAT_LIST @
 [ 56832 ,code 546 ,code ]
MR3040_SETLIST
24 noop
MR3040_SELECTMATRIX
CLOCK @
MR3040_CLOCK
3 noop
FREQUENCY_BUFFER
[ 56832 ,code 24 ,code ] 15 far@
[ 56832 ,code 26 ,code ] 15 far@
   
PB_INDEX @
2* PB_KHZ +
@
 +
[ 56832 ,code 28 ,code ] 15 far@
   
PB_INDEX @
2* PB_HZ +
@
 +
[ 56832 ,code 30 ,code ] 15 far@
FREQUENCY
PB_INDEX @
2* PB_FREQ +
@
OFFSET_FREQUENCY
RESET_FREQUENCY
 [ 56832 ,code 5200 ,code ]
WAITTIMER
 [ 56832 ,code 546 ,code ]
MR3040_START
[ 56832 ,code 152 ,code ] 15 far@
   
0 noop
 >
IF
[ 56832 ,code 154 ,code ] 15 far@
USEROUT
THEN
[ 56832 ,code 44 ,code ] 15 far@
0 noop
RFNUM_SAT @
2* RBD +
@
SET_BOARD_MULTIPLIERS
RFNUM_SAT @
2* RAD +
@
RFNUM_SAT @
2* RBD +
@
   
4 noop
 +
SET3031ADDRESS
RFNUM_SAT @
2* RWT +
@
RFNUM_SAT @
2* RBD +
@
   
4 noop
 +
SET3031WAITS
RFNUM_SAT @
2* RBD +
@
   
4 noop
 +
APPEND_BOARDS_READY
0 noop
RFAMPON
WARMUP @
   
10 noop
 >
IF
WARMUP @
 2- us 0.7us
THEN
[ 56832 ,code 14 ,code ] 15 far@
RFON
MR3031_GO
STARTTIMER
0 noop
2* SAT_ON_AR +
@
 h0=
 0-
0 noop
2* SAT_ON_AR +
!
1 noop
2* SAT_ON_AR +
@
 h0=
 0-
1 noop
2* SAT_ON_AR +
!
2 noop
2* SAT_ON_AR +
@
 h0=
 0-
2 noop
2* SAT_ON_AR +
!
 [ 56832 ,code 280 ,code ]
0 noop
2* SAT_ON_AR +
@
   
[ 56832 ,code 42 ,code ] 15 far@
 [ 45207 ,code 48662 ,code ] swapdrop
1 noop
2* SAT_ON_AR +
@
   
[ 56832 ,code 42 ,code ] 15 far@
 [ 45207 ,code 48662 ,code ] swapdrop
2 noop
2* SAT_ON_AR +
@
   
[ 56832 ,code 42 ,code ] 15 far@
 [ 45207 ,code 48662 ,code ] swapdrop
CREATEMATRIXTEST
IF
                                      XGOTO 0
THEN
TSEL_SAT @
   
 [ 56832 ,code 500 ,code ]
 -
RET !
 [ 56832 ,code 5000 ,code ]
WAITTIMER
RET @
 2- us 0.7us
0 noop
RFON
 [ 56832 ,code 546 ,code ]
MR3040_CONTINUE
[ 56832 ,code 152 ,code ] 15 far@
   
0 noop
 >
IF
[ 56832 ,code 156 ,code ] 15 far@
USEROUT
THEN
TRAMP @
 2- us 0.7us
[ 56832 ,code 40 ,code ] 15 far@
3- us 0.9us
 [ 56832 ,code 546 ,code ]
MR3040_CONTINUE
STARTTIMER
TRAMP @
   
10 noop
 [ 45207 ,code 48662 ,code ] swapdrop
RET !
0 noop
FREQUENCY_BUFFER
RESET_FREQUENCY
RET @
WAITTIMER
[ 56832 ,code 84 ,code ] 15 far@
3- us 0.9us
THEN
PB_INDEX @
   
1 noop
 +
PB_INDEX !
PB_INDEX @
   
6 noop
 =
 UNTIL
THEN
[ 56832 ,code 124 ,code ] 15 far@
IF
STARTTIMER
4 noop
FREQUENCY_BUFFER
RESET_FREQUENCY
 [ 56832 ,code 300 ,code ]
WAITTIMER
[ 56832 ,code 152 ,code ] 15 far@
   
0 noop
 >
IF
[ 56832 ,code 154 ,code ] 15 far@
USEROUT
THEN
[ 56832 ,code 126 ,code ] 15 far@
   
0 noop
 >
IF
[ 56832 ,code 128 ,code ] 15 far@
0 noop
CHESS_RFNUM @
2* RBD +
@
SET_BOARD_MULTIPLIERS
CHESS_RFNUM @
2* RAD +
@
CHESS_RFNUM @
2* RBD +
@
   
4 noop
 +
SET3031ADDRESS
CHESS_RFNUM @
2* RWT +
@
CHESS_RFNUM @
2* RBD +
@
   
4 noop
 +
SET3031WAITS
CHESS_RFNUM @
2* RBD +
@
   
4 noop
 +
APPEND_BOARDS_READY
0 noop
RFAMPON
WARMUP @
   
10 noop
 >
IF
WARMUP @
 2- us 0.7us
THEN
[ 56832 ,code 14 ,code ] 15 far@
RFON
MR3031_GO
STARTTIMER
CHESS_LIST @
 [ 56832 ,code 512 ,code ]
MR3040_SETLIST
6 noop
MR3040_SELECTMATRIX
CLOCK @
MR3040_CLOCK
T_CHESS_GAUSS @
   
1 noop
 -
RET !
 [ 56832 ,code 10000 ,code ]
WAITTIMER
RET @
0.8us ms
0 noop
RFON
 ELSE
0 noop
0 noop
 [ 56832 ,code -232 ,code ]
Set_board_Multipliers
[ 56832 ,code 128 ,code ] 15 far@
0 noop
 [ 56832 ,code -240 ,code ]
Set_board_Multipliers
0 noop
20 noop
 [ 56832 ,code -236 ,code ]
 [ 56832 ,code -228 ,code ]
Set_addr_and_waits
 [ 56832 ,code -236 ,code ]
Append_Boards_Ready
 [ 56832 ,code -228 ,code ]
Append_Boards_Ready
0 noop
RFAMPON
WARMUP @
   
10 noop
 >
IF
WARMUP @
 2- us 0.7us
THEN
[ 56832 ,code 14 ,code ] 15 far@
RFON
MR3031_GO
STARTTIMER
CHESS_LIST @
 [ 56832 ,code 512 ,code ]
MR3040_SETLIST
6 noop
MR3040_SELECTMATRIX
CLOCK @
MR3040_CLOCK
[ 56832 ,code 118 ,code ] 15 far@
   
10 noop
 [ 45207 ,code 48662 ,code ] swapdrop
RET !
RET @
WAITTIMER
RFOFF
0 noop
0 noop
 [ 56832 ,code -232 ,code ]
Set_board_Multipliers
0 noop
0 noop
 [ 56832 ,code -240 ,code ]
Set_board_Multipliers
8 noop
20 noop
 [ 56832 ,code -236 ,code ]
 [ 56832 ,code -228 ,code ]
Set_addr_and_waits
 [ 56832 ,code -236 ,code ]
Append_Boards_Ready
 [ 56832 ,code -228 ,code ]
Append_Boards_Ready
MR3031_GO
THEN
[ 56832 ,code 152 ,code ] 15 far@
   
0 noop
 >
IF
[ 56832 ,code 156 ,code ] 15 far@
USEROUT
THEN
 [ 56832 ,code 512 ,code ]
MR3040_START
STARTTIMER
TRAMP @
   
10 noop
 [ 45207 ,code 48662 ,code ] swapdrop
RET !
0 noop
FREQUENCY_BUFFER
RESET_FREQUENCY
RET @
WAITTIMER
[ 56832 ,code 116 ,code ] 15 far@
3- us 0.9us
TRAMP @
 2- us 0.7us
THEN
SLICE_LIST @
 [ 56832 ,code 512 ,code ]
MR3040_SETLIST
READ_PRE_LIST @
2 noop
MR3040_SETLIST
23 noop
MR3040_SELECTMATRIX
CLOCK @
MR3040_CLOCK
 [ 56832 ,code 514 ,code ]
MR3040_START
TRAMP @
   
 [ 56832 ,code 40 ,code ]
 -
   
[ 56832 ,code 130 ,code ] 15 far@
 +
   
[ 56832 ,code 132 ,code ] 15 far@
   
17 noop
 -
 -
TEMP_MAC !
STARTTIMER
[ 56832 ,code 152 ,code ] 15 far@
   
0 noop
 >
IF
[ 56832 ,code 154 ,code ] 15 far@
USEROUT
THEN
TEMP_MAC @
   
10 noop
 [ 45207 ,code 48662 ,code ] swapdrop
RET !
RET @
WAITTIMER
[ 56832 ,code 58 ,code ] 15 far@
0 noop
RFNUM @
2* RBD +
@
SET_BOARD_MULTIPLIERS
RFNUM @
2* RAD +
@
RFNUM @
2* RBD +
@
   
4 noop
 +
SET3031ADDRESS
RFNUM @
2* RWT +
@
RFNUM @
2* RBD +
@
   
4 noop
 +
SET3031WAITS
RFNUM @
2* RBD +
@
   
4 noop
 +
APPEND_BOARDS_READY
0 noop
RFAMPON
WARMUP @
   
10 noop
 >
IF
WARMUP @
 2- us 0.7us
THEN
STARTTIMER
[ 56832 ,code 132 ,code ] 15 far@
   
17 noop
 -
   
10 noop
 [ 45207 ,code 48662 ,code ] swapdrop
RET !
RET @
WAITTIMER
[ 56832 ,code 14 ,code ] 15 far@
RFON
MR3031_GO
TSEL90 @
   
3 noop
 -
   
[ 56832 ,code 130 ,code ] 15 far@
 -
RET !
RET @
 2- us 0.7us
 [ 56832 ,code 514 ,code ]
MR3040_CONTINUE
STARTTIMER
[ 56832 ,code 130 ,code ] 15 far@
   
10 noop
 [ 45207 ,code 48662 ,code ] swapdrop
RET !
RET @
WAITTIMER
0 noop
RFON
[ 56832 ,code 152 ,code ] 15 far@
   
0 noop
 >
IF
[ 56832 ,code 156 ,code ] 15 far@
USEROUT
THEN
TRAMP @
   
3 noop
 [ 45207 ,code 48662 ,code ] swapdrop
   
TREF @
 +
INTTOLONG
TEMPL3 2!
TEMPL3 q2@
   
 [ 56832 ,code 10 ,code 56832 ,code 0 ,code  ]
 D*
TEMPL3 2!
RESYNC
PHASE_180 @
   
[ 56832 ,code 134 ,code ] 15 far@
 -
PHASE
[ 56832 ,code 180 ,code ] 15 far@
   
0 noop
 =
IF
TE_BALANCE_AL q2@
   
 [ 56832 ,code -27 ,code ]
   
[ 56832 ,code 76 ,code ] 15 far@
 +
INTTOLONG
 D+
POST_90_DELAY0L 2!
POST_90_DELAY0L q2@
   
 [ 56832 ,code 10 ,code 56832 ,code 0 ,code  ]
 D*
POST_90_DELAY0L 2!
POST_90_DELAY0L q2@
PRE_90_DELAY0L 2!
 ELSE
TE_BALANCE_AL q2@
   
 [ 56832 ,code -27 ,code ]
   
[ 56832 ,code 76 ,code ] 15 far@
 +
INTTOLONG
 D+
   
SM_DELTA_US q2@
 D-
   
DIFF_TRAMP @
S>D
 D-
POST_90_DELAY0L 2!
POST_90_DELAY0L q2@
   
 [ 56832 ,code 10 ,code 56832 ,code 0 ,code  ]
 D*
   
EXTRA_DELTA_US q2@
 D-
   
 [ 56832 ,code 185 ,code ]
S>D
 D-
POST_90_DELAY0L 2!
POST_90_DELAY0L q2@
PRE_90_DELAY0L 2!
THEN
FLOW_COMP_ON @
IF
POST_90_DELAY0L q2@
   
20 noop
   
TRAMP @
 [ 45207 ,code 48662 ,code ] swapdrop
   
5 noop
   
TSEL90 @
 [ 45207 ,code 48662 ,code ] swapdrop
 +
INTTOLONG
 D+
POST_90_DELAY0L 2!
THEN
TEMPL3 q2@
   
 [ 56832 ,code -16536 ,code 56832 ,code 0 ,code  ]
 D>
IF
TEMPL3 q2@
   
10 noop
S>D
 D/
   
 [ 56832 ,code 4800 ,code ]
S>D
 D-
DROP
RET !
 [ 56832 ,code -17561 ,code 56832 ,code 0 ,code  ]
DROP
WAITTIMER
RET @
 2- us 0.7us
 ELSE
TEMPL3 q2@
   
25 noop
S>D
 D-
DROP
WAITTIMER
THEN
POST_90_DELAY0L q2@
   
 [ 56832 ,code 25 ,code 56832 ,code 0 ,code  ]
 D>
IF
POST_90_DELAY0L q2@
DELAY32
THEN
STARTTIMER
SLICE_180_REFOCUS @
 [ 56832 ,code 512 ,code ]
MR3040_SETLIST
21 noop
MR3040_SELECTMATRIX
GP_SL_INC @
 0-
   
 [ 56832 ,code 2048 ,code ]
   
CURRENT_VIEW_2 @
 +
5 noop
PR
 [ 45207 ,code 48662 ,code ] swapdrop
GP_SL_VAR !
 [ 56832 ,code 210 ,code ]
WAITTIMER
[ 56832 ,code 180 ,code ] 15 far@
IF
CLOCK @
MR3040_CLOCK
 [ 56832 ,code 60 ,code ]
MR3040_SELECTMATRIX
DIFF_LIST @
 [ 56832 ,code 546 ,code ]
MR3040_SETLIST
 [ 56832 ,code 546 ,code ]
MR3040_START
SM_DELTA_US q2@
DROP
 2- us 0.7us
 [ 56832 ,code 546 ,code ]
MR3040_CONTINUE
TRAMP @
 2- us 0.7us
EXTRA_DELTA_US q2@
   
25 noop
S>D
 D>
IF
EXTRA_DELTA_US q2@
DELAY32
THEN
ECHO_CNT @
   
VIEWS_PER_SEG @
 <
IF
SLICE_180_REFOCUS @
 [ 56832 ,code 512 ,code ]
MR3040_SETLIST
THEN
THEN
LABEL 29
21 noop
MR3040_SELECTMATRIX
 [ 56832 ,code 512 ,code ]
MR3040_START
[ 56832 ,code 12 ,code ] 15 far@
   
TRAMP @
 +
   
 [ 56832 ,code 40 ,code ]
 -
   
[ 56832 ,code 130 ,code ] 15 far@
 +
   
[ 56832 ,code 132 ,code ] 15 far@
   
17 noop
 -
 -
TEMP_MAC !
STARTTIMER
[ 56832 ,code 152 ,code ] 15 far@
   
0 noop
 >
IF
[ 56832 ,code 154 ,code ] 15 far@
USEROUT
THEN
TEMP_MAC @
   
10 noop
 [ 45207 ,code 48662 ,code ] swapdrop
RET !
RET @
WAITTIMER
[ 56832 ,code 60 ,code ] 15 far@
0 noop
RFNUM @
2* RBD +
@
SET_BOARD_MULTIPLIERS
RFNUM @
2* RAD +
@
RFNUM @
2* RBD +
@
   
4 noop
 +
SET3031ADDRESS
RFNUM @
2* RWT +
@
RFNUM @
2* RBD +
@
   
4 noop
 +
SET3031WAITS
RFNUM @
2* RBD +
@
   
4 noop
 +
APPEND_BOARDS_READY
0 noop
RFAMPON
WARMUP @
   
10 noop
 >
IF
WARMUP @
 2- us 0.7us
THEN
STARTTIMER
[ 56832 ,code 132 ,code ] 15 far@
   
17 noop
 -
   
10 noop
 [ 45207 ,code 48662 ,code ] swapdrop
RET !
RET @
WAITTIMER
[ 56832 ,code 14 ,code ] 15 far@
RFON
MR3031_GO
STARTTIMER
TOTAL_ECHO_CNT @
   
[ 56832 ,code 108 ,code ] 15 far@
 <
DISCARD_CURRENT_ECHO !
DISCARD_CURRENT_ECHO @
IF
0 noop
GP_MUL !
 ELSE
 [ 56832 ,code 1024 ,code ]
   
CURRENT_VIEW @
 +
   
ECHO_CNT @
 +
5 noop
PR
GP_MUL !
THEN
GP_INC @
 0-
   
GP_MUL @
 [ 45207 ,code 48662 ,code ] swapdrop
   
NAV_CNT @
 [ 45207 ,code 48662 ,code ] swapdrop
GP_VAR !
 [ 56832 ,code 259 ,code ]
[ 56832 ,code 56 ,code ] 15 far@
   
GSP_RP @
   
GP_SL_VAR @
   
GP_SL_ON @
 [ 45207 ,code 48662 ,code ] swapdrop
   
NAV_CNT @
 [ 45207 ,code 48662 ,code ] swapdrop
 -
 [ 45207 ,code 48662 ,code ] swapdrop
[ 56832 ,code 54 ,code ] 15 far@
   
GP_VAR @
 [ 45207 ,code 48662 ,code ] swapdrop
[ 56832 ,code 52 ,code ] 15 far@
   
GR_DP @
 [ 45207 ,code 48662 ,code ] swapdrop
CREATEMATRIXTEST
IF
                                      XGOTO 0
THEN
TSEL90 @
   
 [ 56832 ,code 300 ,code ]
 <
IF
TSEL90 @
   
10 noop
 [ 45207 ,code 48662 ,code ] swapdrop
RET !
RET @
WAITTIMER
 ELSE
 [ 56832 ,code 2975 ,code ]
RET !
TSEL90 @
INTTOLONG
   
10 noop
S>D
 D*
   
 [ 56832 ,code 3000 ,code ]
S>D
 D-
RF_EXTEND_DELAY 2!
RET @
WAITTIMER
RF_EXTEND_DELAY q2@
   
25 noop
S>D
 D>
IF
RF_EXTEND_DELAY q2@
DELAY32
THEN
THEN
STARTTIMER
0 noop
RFON
TRAMP @
   
[ 56832 ,code 12 ,code ] 15 far@
 +
   
[ 56832 ,code 130 ,code ] 15 far@
 -
   
10 noop
 [ 45207 ,code 48662 ,code ] swapdrop
RET !
[ 56832 ,code 152 ,code ] 15 far@
   
0 noop
 >
IF
[ 56832 ,code 156 ,code ] 15 far@
USEROUT
THEN
RET @
WAITTIMER
[ 56832 ,code 180 ,code ] 15 far@
   
TOTAL_ECHO_CNT @
   
0 noop
 =
 &&
IF
EXTRA_DELTA_US q2@
   
25 noop
S>D
 D>
IF
EXTRA_DELTA_US q2@
DELAY32
THEN
CLOCK @
MR3040_CLOCK
 [ 56832 ,code 60 ,code ]
MR3040_SELECTMATRIX
DIFF_LIST @
 [ 56832 ,code 546 ,code ]
MR3040_SETLIST
 [ 56832 ,code 546 ,code ]
MR3040_START
SM_DELTA_US q2@
DROP
 2- us 0.7us
 [ 56832 ,code 546 ,code ]
MR3040_CONTINUE
TRAMP @
 2- us 0.7us
THEN
DE_ON @
   
ECHO_CNT @
   
VIEWS_PER_SEG @
 =
 &&
IF
                                      XGOTO 30
THEN
STARTTIMER
0 noop
TEMP !
TOTAL_ECHO_CNT @
   
0 noop
 =
IF
0 noop
TEMP !
THEN
3 noop
MR3040_SELECTMATRIX
READ_LIST @
2 noop
MR3040_SETLIST
PHASE_LIST @
 [ 56832 ,code 32 ,code ]
MR3040_SETLIST
SLICE_LIST_RP @
 [ 56832 ,code 512 ,code ]
MR3040_SETLIST
 [ 56832 ,code 210 ,code ]
   
TEMP @
 +
   
25 noop
 -
WAITTIMER
[ 56832 ,code 180 ,code ] 15 far@
IF
TE_BALANCE_BL_TEMP1 q2@
   
25 noop
S>D
 D>
IF
TOTAL_ECHO_CNT @
   
0 noop
 =
IF
TE_BALANCE_BL_TEMP1 q2@
   
SM_DELTA_US q2@
   
 [ 56832 ,code 10 ,code 56832 ,code 0 ,code  ]
 D*
 D-
   
EXTRA_DELTA_US q2@
 D-
   
DIFF_TRAMP @
S>D
 [ 56832 ,code 10 ,code 56832 ,code 0 ,code  ]
 D*
 D-
   
 [ 56832 ,code 156 ,code 56832 ,code 0 ,code  ]
 D-
TEMPL1 2!
TEMPL1 q2@
   
 [ 56832 ,code 25 ,code 56832 ,code 0 ,code  ]
 D>
IF
TEMPL1 q2@
DELAY32
 ELSE
." Timing error (="
TEMPL1 q2@
 D.
." )!"
 CR
THEN
 ELSE
TE_BALANCE_BL_TEMP1_ESP q2@
   
25 noop
S>D
 D>
IF
TE_BALANCE_BL_TEMP1_ESP q2@
DELAY32
THEN
THEN
THEN
 ELSE
TE_BALANCE_BL_TEMP1 q2@
DELAY32
THEN
 [ 56832 ,code 546 ,code ]
MR3040_START
STARTTIMER
3 noop
[ 56832 ,code 56 ,code ] 15 far@
   
GS_VAR_RESCALE @
 [ 45207 ,code 48662 ,code ] swapdrop
[ 56832 ,code 54 ,code ] 15 far@
   
GP_VAR @
 [ 45207 ,code 48662 ,code ] swapdrop
[ 56832 ,code 52 ,code ] 15 far@
   
GR_UNDERSAMPLE @
 [ 45207 ,code 48662 ,code ] swapdrop
   
GR_VAR @
   
GR_OVERSAMPLE @
 /
 [ 45207 ,code 48662 ,code ] swapdrop
CREATEMATRIXTEST
IF
                                      XGOTO 0
THEN
FOV_PHASE_DEG @
INTTOLONG
   
GP_MUL @
INTTOLONG
 D*
TEMPL1 2!
TEMPL1 q2@
   
 [ 56832 ,code 2048 ,code ]
   
CURRENT_VIEW_2 @
 +
5 noop
PR
INTTOLONG
   
FOV_SL_PHASE_DEG @
INTTOLONG
 D*
 D+
TEMPL1 2!
TEMPL1 q2@
   
DEG_360 @
S>D
 D/REM
DROP
PHASE_REC !
PHASE_REC @
   
NAV_CNT @
 [ 45207 ,code 48662 ,code ] swapdrop
PHASE_REC !
[ 56832 ,code 54 ,code ] 15 far@
   
0 noop
 =
IF
0 noop
PHASE_REC !
THEN
TRAMP @
   
20 noop
 [ 45207 ,code 48662 ,code ] swapdrop
   
TDP @
   
10 noop
 [ 45207 ,code 48662 ,code ] swapdrop
 +
RET !
PHASE_REC @
   
PHASE_CORRECTION @
 +
RPHASE
DISCARD_CURRENT_ECHO @
IF
1 noop
DUMMY_CYCLES
 ELSE
0 noop
DUMMY_CYCLES
ECHO_CNT @
   
1 noop
 +
ECHO_CNT !
THEN
[ 56832 ,code 142 ,code ] 15 far@
   
[ 56832 ,code 140 ,code ] 15 far@
 < NOT
 0-
[ 56832 ,code 144 ,code ] 15 far!
[ 56832 ,code 144 ,code ] 15 far@
 h0=
DUMMY_CYCLES
RET @
WAITTIMER
STARTTIMER
RESYNC
1 noop
FREQUENCY_BUFFER
RESET_FREQUENCY
TRAMP @
   
[ 56832 ,code 130 ,code ] 15 far@
 +
   
10 noop
 [ 45207 ,code 48662 ,code ] swapdrop
RET !
RET @
WAITTIMER
SAMPLE_PERIOD @
INITIATE
STARTTIMER
 [ 56832 ,code 259 ,code ]
[ 56832 ,code 56 ,code ] 15 far@
   
GSP_RP @
   
GP_SL_VAR @
   
GP_SL_ON @
 [ 45207 ,code 48662 ,code ] swapdrop
   
NAV_CNT @
 [ 45207 ,code 48662 ,code ] swapdrop
 +
 [ 45207 ,code 48662 ,code ] swapdrop
[ 56832 ,code 54 ,code ] 15 far@
   
GP_VAR @
 [ 45207 ,code 48662 ,code ] swapdrop
[ 56832 ,code 52 ,code ] 15 far@
   
GR_DP @
 [ 45207 ,code 48662 ,code ] swapdrop
CREATEMATRIXTEST
IF
                                      XGOTO 0
THEN
PHASE_ANG q2@
TEMPL1 2!
TOTAL_ECHO_CNT @
   
1 noop
 +
TOTAL_ECHO_CNT !
TOTAL_ECHO_CNT @
INTTOLONG
TEMPL2 2!
TEMPL1 q2@
   
TEMPL2 q2@
 D*
   
0 noop
   
[ 56832 ,code 134 ,code ] 15 far@
 [ 45207 ,code 48662 ,code ] swapdrop
S>D
 D+
TEMPL3 2!
TEMPL3 q2@
   
DEG_360 @
INTTOLONG
 D/REM
DROP
PHASE_CORRECTION_0 !
TEMPL2 q2@
   
REMAINDER_PHASE @
INTTOLONG
 D*
TEMPL5 2!
TEMPL5 q2@
   
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D/
TEMPL4 2!
TEMPL4 q2@
DROP
PHASE_CORRECTION_1 !
TEMPL5 q2@
   
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D/REM
TEMPL4 2!
0 noop
PHASE_CORRECTION_2 !
TEMPL4 q2@
   
 [ 56832 ,code 500 ,code ]
S>D
 D>
IF
1 noop
PHASE_CORRECTION_2 !
THEN
TEMPL4 q2@
   
 [ 56832 ,code -500 ,code ]
S>D
 D<
IF
 [ 56832 ,code -1 ,code ]
PHASE_CORRECTION_2 !
THEN
PHASE_CORRECTION_0 @
   
PHASE_CORRECTION_1 @
 +
   
PHASE_CORRECTION_2 @
 +
   
DEG_360 @
 n/rem
PHASE_CORRECTION !
NO_SAMPLES @
   
NO_DISCARD @
 +
INTTOLONG
   
SAMPLE_PERIOD @
INTTOLONG
 D*
   
 [ 56832 ,code 3 ,code 56832 ,code 0 ,code  ]
 D-
TEMPL1 2!
 [ 56832 ,code 8997 ,code ]
RET !
TEMPL1 q2@
   
RET @
S>D
 D<
IF
." Sampling time too short"
 CR
THEN
TEMPL1 q2@
   
RET @
S>D
 D-
TEMPL1 2!
TEMPL1 q2@
   
 [ 56832 ,code 10000 ,code 56832 ,code 0 ,code  ]
 D/
TEMPL2 2!
TEMPL2 q2@
   
1 noop
S>D
 D<
IF
." Sampling time incompatible "
 CR
THEN
TEMPL1 q2@
   
10 noop
S>D
 D/
   
TEMPL2 q2@
   
 [ 56832 ,code 1000 ,code 56832 ,code 0 ,code  ]
 D*
 D-
TEMPL3 2!
SAMPLE_PERIOD @
   
 [ 56832 ,code 250 ,code ]
 =
IF
TEMPL3 q2@
   
1 noop
S>D
 D-
TEMPL3 2!
THEN
TEMPL3 q2@
   
10 noop
S>D
 D<
IF
." Sampling time incompatible "
 CR
THEN
RET @
WAITTIMER
TEMPL2 q2@
DROP
0.8us ms
TEMPL3 q2@
DROP
 2- us 0.7us
COMPLETE
STARTTIMER
RESYNC
0 noop
FREQUENCY_BUFFER
RESET_FREQUENCY
PHASE_180 @
   
PHASE_CORRECTION @
 +
PHASE
GETTIMER
   
 [ 56832 ,code 250 ,code ]
 +
RET !
TE_BALANCE_BL_TEMP2 q2@
TEMPL3 2!
ECHO_CNT @
   
VIEWS_PER_SEG @
   
DE_ON @
 +
 <
IF
TEMPL3 q2@
   
TE_BALANCE_BL_ESP q2@
 D+
TEMPL3 2!
THEN
TEMPL3 q2@
   
 [ 56832 ,code 10 ,code 56832 ,code 0 ,code  ]
 D*
   
RET @
S>D
 D-
TEMPL3 2!
RET @
   
25 noop
 +
RET !
RET @
   
25 noop
 -
WAITTIMER
[ 56832 ,code 180 ,code ] 15 far@
IF
TOTAL_ECHO_CNT @
   
0 noop
 =
IF
TRAMP @
 2- us 0.7us
[ 56832 ,code 78 ,code ] 15 far@
3- us 0.9us
 ELSE
TEMPL3 q2@
   
25 noop
S>D
 D>
IF
TEMPL3 q2@
DELAY32
THEN
THEN
THEN
[ 56832 ,code 180 ,code ] 15 far@
   
0 noop
 =
IF
TEMPL3 q2@
   
25 noop
S>D
 D>
IF
TEMPL3 q2@
DELAY32
THEN
THEN
STARTTIMER
ECHO_CNT @
   
VIEWS_PER_SEG @
   
DE_ON @
 +
 <
IF
SLICE_180_REFOCUS @
 [ 56832 ,code 512 ,code ]
MR3040_SETLIST
THEN
ECHO_CNT @
   
VIEWS_PER_SEG @
   
DE_ON @
 +
 <
IF
 [ 56832 ,code 210 ,code ]
WAITTIMER
XGOTO 29
THEN
 [ 56832 ,code 210 ,code ]
RET !
RET @
WAITTIMER
LABEL 30
DE_ON @
   
1 noop
 =
IF
PRE_90_DELAY0L q2@
   
25 noop
S>D
 D>
IF
PRE_90_DELAY0L q2@
DELAY32
THEN
STARTTIMER
SLICE_DE90_LIST @
 [ 56832 ,code 512 ,code ]
MR3040_SETLIST
READ_DE90_LIST @
2 noop
MR3040_SETLIST
23 noop
MR3040_SELECTMATRIX
CLOCK @
MR3040_CLOCK
 [ 56832 ,code 210 ,code ]
WAITTIMER
 [ 56832 ,code 514 ,code ]
MR3040_START
STARTTIMER
2 noop
   
DEG_90 @
 [ 45207 ,code 48662 ,code ] swapdrop
   
PHASE_180 @
 -
   
PHASE_CORRECTION @
 -
   
[ 56832 ,code 74 ,code ] 15 far@
 +
PHASE
20 noop
   
TRAMP @
 [ 45207 ,code 48662 ,code ] swapdrop
RET !
FLOW_COMP_ON @
IF
2 noop
   
RET @
 [ 45207 ,code 48662 ,code ] swapdrop
   
5 noop
   
TSEL90 @
 [ 45207 ,code 48662 ,code ] swapdrop
 +
RET !
THEN
RET @
WAITTIMER
TREF @
 2- us 0.7us
TRAMP @
   
 [ 56832 ,code 40 ,code ]
 -
   
[ 56832 ,code 130 ,code ] 15 far@
 +
   
[ 56832 ,code 132 ,code ] 15 far@
   
17 noop
 -
 -
TEMP_MAC !
STARTTIMER
[ 56832 ,code 152 ,code ] 15 far@
   
0 noop
 >
IF
[ 56832 ,code 154 ,code ] 15 far@
USEROUT
THEN
TEMP_MAC @
   
10 noop
 [ 45207 ,code 48662 ,code ] swapdrop
RET !
RET @
WAITTIMER
[ 56832 ,code 58 ,code ] 15 far@
0 noop
RFNUM @
2* RBD +
@
SET_BOARD_MULTIPLIERS
RFNUM @
2* RAD +
@
RFNUM @
2* RBD +
@
   
4 noop
 +
SET3031ADDRESS
RFNUM @
2* RWT +
@
RFNUM @
2* RBD +
@
   
4 noop
 +
SET3031WAITS
RFNUM @
2* RBD +
@
   
4 noop
 +
APPEND_BOARDS_READY
0 noop
RFAMPON
WARMUP @
   
10 noop
 >
IF
WARMUP @
 2- us 0.7us
THEN
STARTTIMER
[ 56832 ,code 132 ,code ] 15 far@
   
17 noop
 -
   
10 noop
 [ 45207 ,code 48662 ,code ] swapdrop
RET !
RET @
WAITTIMER
[ 56832 ,code 14 ,code ] 15 far@
RFON
MR3031_GO
TSEL90 @
   
3 noop
 -
   
[ 56832 ,code 130 ,code ] 15 far@
 -
RET !
RET @
 2- us 0.7us
 [ 56832 ,code 512 ,code ]
MR3040_CONTINUE
STARTTIMER
[ 56832 ,code 130 ,code ] 15 far@
   
10 noop
 [ 45207 ,code 48662 ,code ] swapdrop
RET !
RET @
WAITTIMER
0 noop
RFON
[ 56832 ,code 152 ,code ] 15 far@
   
0 noop
 >
IF
[ 56832 ,code 156 ,code ] 15 far@
USEROUT
THEN
TRAMP @
   
10 noop
 [ 45207 ,code 48662 ,code ] swapdrop
RET !
RET @
WAITTIMER
THEN
[ 56832 ,code 96 ,code ] 15 far@
IF
30 noop
[ 56832 ,code 56 ,code ] 15 far@
 0-
   
[ 56832 ,code 100 ,code ] 15 far@
 [ 45207 ,code 48662 ,code ] swapdrop
[ 56832 ,code 54 ,code ] 15 far@
 0-
   
[ 56832 ,code 100 ,code ] 15 far@
 [ 45207 ,code 48662 ,code ] swapdrop
[ 56832 ,code 52 ,code ] 15 far@
 0-
   
[ 56832 ,code 100 ,code ] 15 far@
 [ 45207 ,code 48662 ,code ] swapdrop
CREATEMATRIXTEST
IF
                                      XGOTO 0
THEN
[ 56832 ,code 99 ,code ] us
30 noop
MR3040_SELECTMATRIX
POST_CRUSH_LIST @
 [ 56832 ,code 546 ,code ]
MR3040_SETLIST
 [ 56832 ,code 546 ,code ]
MR3040_START
TRAMP @
   
TRAMP @
 +
   
[ 56832 ,code 98 ,code ] 15 far@
 +
RET !
RET @
 2- us 0.7us
THEN
STARTTIMER
0 noop
S>D
TEMPL1 2!
[ 56832 ,code 34 ,code ] 15 far@
   
1 noop
 =
   
GATING_AFTER_TR_ON @
   
1 noop
 =
 &&
IF
[ 56832 ,code 112 ,code ] 15 far@
   
0 noop
 =
IF
TR_EXTEND_USL q2@
   
TIME @
INTTOLONG
   
 [ 56832 ,code 10000 ,code 56832 ,code 0 ,code  ]
 D*
 D-
TEMPL1 2!
THEN
THEN
[ 56832 ,code 34 ,code ] 15 far@
   
0 noop
 =
IF
TIME @
   
10 noop
 >
IF
0 noop
TIME !
THEN
[ 56832 ,code 112 ,code ] 15 far@
   
0 noop
 =
IF
TR_EXTEND_USL q2@
   
TIME @
INTTOLONG
   
 [ 56832 ,code 10000 ,code 56832 ,code 0 ,code  ]
 D*
 D-
TEMPL1 2!
 ELSE
CURRENT_SLICE @
   
SLICE_BATCH_START @
   
BATCH_SLICES @
 +
 =
IF
[ 56832 ,code 2 ,code ] 15 far@
S>D
TR_MIN q2@
   
[ 56832 ,code 148 ,code ] 15 far@
S>D
 D+
   
BATCH_SLICES @
S>D
 D*
 D-
DROP
TR_EXTEND !
TR_EXTEND @
INTTOLONG
   
 [ 56832 ,code 10000 ,code 56832 ,code 0 ,code  ]
 D*
TEMPL1 2!
THEN
THEN
THEN
 [ 56832 ,code 690 ,code ]
WAITTIMER
TEMPL1 q2@
   
 [ 56832 ,code 25 ,code 56832 ,code 0 ,code  ]
 D>
IF
TEMPL1 q2@
DELAY32
THEN
[ 56832 ,code 34 ,code ] 15 far@
   
1 noop
 =
   
[ 56832 ,code 148 ,code ] 15 far@
   
0 noop
 >
 &&
IF
[ 56832 ,code 148 ,code ] 15 far@
ms
THEN
STARTTIMER
NO_ACQ @
   
1 noop
 +
NO_ACQ !
SLICE_AV @
   
1 noop
 +
SLICE_AV !
SLICE_AV @
   
SLICE_BLOCK @
 <
IF
XGOTO 27
THEN
CURRENT_SLICE @
   
SLICE_BATCH_START @
   
BATCH_SLICES @
 +
 <
IF
XGOTO 26
THEN
[ 56832 ,code 142 ,code ] 15 far@
   
1 noop
 +
[ 56832 ,code 142 ,code ] 15 far!
[ 56832 ,code 142 ,code ] 15 far@
   
[ 56832 ,code 140 ,code ] 15 far@
 > NOT
IF
XGOTO 22
 ELSE
[ 56832 ,code 140 ,code ] 15 far@
[ 56832 ,code 142 ,code ] 15 far!
THEN
VIEW_AV @
   
SLICE_BLOCK @
 +
VIEW_AV !
VIEW_AV @
   
VIEW_BLOCK @
 <
IF
XGOTO 25
THEN
CURRENT_VIEW_2 @
   
1 noop
 +
CURRENT_VIEW_2 !
CURRENT_VIEW_2 @
   
NO_VIEWS_2 @
 <
IF
XGOTO 24
THEN
CURRENT_VIEW @
   
VIEWS_PER_SEG @
 +
CURRENT_VIEW !
NAV_CNT @
   
0 noop
 =
IF
1 noop
NAV_CNT !
THEN
CURRENT_VIEW @
   
NO_VIEWS @
 <
IF
XGOTO 23
THEN
SLICE_BATCH_START @
   
BATCH_SLICES @
 +
SLICE_BATCH_START !
SLICE_BATCH_START @
   
NO_SLICES @
 <
IF
XGOTO 21
THEN
IMAGE_AV @
   
VIEW_BLOCK @
 +
IMAGE_AV !
SETUP_MODE @
   
0 noop
 >
IF
IMAGE_AV @
   
NO_AVERAGES @
 <
IF
XGOTO 13
THEN
THEN
IMAGE_AV @
   
NO_AVERAGES @
 <
IF
XGOTO 15
THEN
COMPLETED_EX @
   
1 noop
 +
COMPLETED_EX !
DIFF_DIR_CNT @
   
1 noop
 +
DIFF_DIR_CNT !
DIFF_DIR_CNT @
   
NO_DIFF_DIR @
 <
IF
XGOTO 20
THEN
B_STEP_CNT @
   
1 noop
 +
B_STEP_CNT !
B_STEP_CNT @
   
NO_B_STEPS @
 <
IF
XGOTO 19
THEN
COMPLETED_EX @
   
NO_EXPERIMENTS @
 <
IF
XGOTO 18
THEN
LABEL 0
 ;
