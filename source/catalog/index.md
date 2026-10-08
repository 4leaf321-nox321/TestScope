# 장비 카탈로그 색인

장비 객체 934 개 · 제조사 185 · 노드 4805 · 엣지 9144

`limits` 는 시리즈 전체 범위. 단위는 키 이름에 있다(kN, mm/min, degC …). 빈 칸은 미기재.

## 3ctest (3C Test Ltd.) (`3ctest`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [3ctest-eds-esd-simulators](equipment/3ctest/3ctest-eds-esd-simulators.json) | 계열 | esd_simulator | esd_immunity | – | – | esd_voltage_kV=0.2–30; discharge_mode=contact, air | limited |

## Admesy (`admesy`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [admesy-asteria](equipment/admesy/admesy-asteria.json) | 계열 | display_color_analyzer | photometry_colorimetry | – | – | luminance_cd_m2=0.005–11000 | limited |
| [admesy-hyperion](equipment/admesy/admesy-hyperion.json) | 계열 | display_color_analyzer | photometry_colorimetry | – | – | luminance_cd_m2=0.0005–12000 | limited |
| [admesy-imaging-colorimeters](equipment/admesy/admesy-imaging-colorimeters.json) | 계열 | imaging_colorimeter | photometry_colorimetry | – | – | luminance_cd_m2=0.005–24000; dynamic_range_dB=60–70 | limited |
| [admesy-prometheus-colorimeters](equipment/admesy/admesy-prometheus-colorimeters.json) | 계열 | display_color_analyzer | photometry_colorimetry | – | – | luminance_cd_m2=0.0001–30000; acceptance_angle_deg=2.5, 4.5 | limited |

## Agilent Technologies (`agilent`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [agilent-5977c-gcms](equipment/agilent/agilent-5977c-gcms.json) | 기종 | chromatograph_mass_spectrometer | composition_analysis | – | – |  | limited |

## AIKOH ENGINEERING Co., Ltd. (`aikoh`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [aikoh-cbl-5s-cord-bending](equipment/aikoh/aikoh-cbl-5s-cord-bending.json) | 계열 | component_life_tester | mechanical_endurance | – | – | cycle_rate_cpm=≤60; fold_angle_deg=≤90; stations=5 | limited |
| [aikoh-sr-switch-endurance](equipment/aikoh/aikoh-sr-switch-endurance.json) | 계열 | component_life_tester | mechanical_endurance | – | – | cycle_rate_cpm=60–600; stroke_mm=≤10; force_N=9.8–49; stations=1, 3, 5 | limited |

## Advanced Instrument Technology (AIT) (`ait`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [ait-cmt-sr-sheet-resistance](equipment/ait/ait-cmt-sr-sheet-resistance.json) | 계열 | electrical_property_tester | electrical_transport | – | – | current_A=1e-08–0.1; voltage_V=0–2.0; wafer_size_mm=≤450; surface_resistivity_ohm_sq=0.001–2000000.0 | catalog |

## Albatross Projects GmbH (`albatross-projects`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [albatross-projects-shielded-rooms](equipment/albatross-projects/albatross-projects-shielded-rooms.json) | 계열 | shielded_enclosure | shielding_effectiveness, emi_emission | – | – | frequency_Hz=70000000–110000000000; insertion_gain=100 | limited |

## Allied Vision Technologies (`allied-vision`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [allied-vision-goldeye](equipment/allied-vision/allied-vision-goldeye.json) | 계열 | high_speed_swir_camera |  | – | – | resolution_pixels=81920–1310720; wavelength_nm=400–2200; frame_rate_fps=94–344; pixel_pitch_um=5, 15, 25, 30; adc_resolution_bit=12, 14 | limited |

## AMETEK / Lloyd Instruments (`ametek-lloyd`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [ametek-lloyd-contacting-and-long-travel-extensometers](equipment/ametek-lloyd/ametek-lloyd-contacting-and-long-travel-extensometers.json) | **센서** | extensometer | tensile, compression, flexure, fatigue | – | – | specimen_thickness_mm=≤25 | limited |
| [ametek-lloyd-load-cells](equipment/ametek-lloyd/ametek-lloyd-load-cells.json) | **센서** | load_cell | tensile, compression, torsion | – | – |  | limited |
| [ametek-lloyd-ls-series](equipment/ametek-lloyd/ametek-lloyd-ls-series.json) | 계열 | universal_testing_machine | tensile, compression, flexure, peel, tear, friction_coefficient, seal_strength | 0.005–5 | – | crosshead_speed_mm_min=0.01–2032; crosshead_travel_mm=500–1400; data_rate_Hz=≤1000 | catalog |
| [ametek-lloyd-pogos-and-splinter-shields](equipment/ametek-lloyd/ametek-lloyd-pogos-and-splinter-shields.json) | **부속** | accessory | tensile, compression | – | – | specimen_size_mm=≤2000 | limited |
| [ametek-lloyd-tcf950-furnace](equipment/ametek-lloyd/ametek-lloyd-tcf950-furnace.json) | **부속** | furnace | tensile, compression | – | 50–950 |  | limited |
| [ametek-lloyd-test-stand-grips-and-fixtures](equipment/ametek-lloyd/ametek-lloyd-test-stand-grips-and-fixtures.json) | **부속** | grip_fixture | tensile, compression, flexure, peel, friction_coefficient, shear | – | -70–180 |  | limited |
| [ametek-lloyd-thermal-cabinets-tc540-tc550](equipment/ametek-lloyd/ametek-lloyd-thermal-cabinets-tc540-tc550.json) | **부속** | environmental_chamber | tensile, compression, flexure | – | -70–300 |  | limited |
| [ametek-lloyd-ve1-video-extensometer](equipment/ametek-lloyd/ametek-lloyd-ve1-video-extensometer.json) | **센서** | extensometer | tensile | – | – | data_rate_Hz=≤100 | limited |

## Anritsu Corporation (`anritsu`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [anritsu-mg3710e](equipment/anritsu/anritsu-mg3710e.json) | 계열 | signal_generator |  | – | – | output_frequency_Hz=100000–6000000000; bandwidth_Hz=≤160000000; rf_output_level_dBm=-144–23; phase_noise_dBc_Hz=-140, -131, -125; channels=1, 2; waveform_memory | catalog |
| [anritsu-mg3740a](equipment/anritsu/anritsu-mg3740a.json) | 계열 | signal_generator |  | – | – | output_frequency_Hz=100000–6000000000; rf_output_level_dBm=-144–23; phase_noise_dBc_Hz=-140, -131, -125; channels=1, 2; bandwidth_Hz=≤2000000; waveform_memory_p | catalog |
| [anritsu-mt8000a](equipment/anritsu/anritsu-mt8000a.json) | 계열 | radio_communication_tester |  | – | – | frequency_Hz=400000000–43500000000; bandwidth_Hz=≤1000000000; rf_port_count=≤4; radio_standards=5G NR (NSA/SA), DSS, NTN, RedCap; rf_output_level_dBm=-110–15 | catalog |
| [anritsu-mt8820c](equipment/anritsu/anritsu-mt8820c.json) | 계열 | radio_communication_tester |  | – | – | frequency_Hz=30000000–2700000000; radio_standards=LTE-Advanced FDD/TDD DL CA, LTE FDD/TDD, W-CDMA/HSPA/HSPA Evolution/DC-HSPA/4C-HSDPA, TD-SCDMA/TD-HSPA/TD-HSDP | limited |
| [anritsu-mt8821c](equipment/anritsu/anritsu-mt8821c.json) | 계열 | radio_communication_tester |  | – | – | frequency_Hz=30000000–6000000000; bandwidth_Hz=≤160000000; radio_standards=LTE/LTE-Advanced, Cat-M1/NB-IoT, NTN NB-IoT, W-CDMA/HSPA, GSM/EGPRS, TD-SCDMA/HSPA, L | catalog |
| [anritsu-mt8852b](equipment/anritsu/anritsu-mt8852b.json) | 계열 | radio_communication_tester |  | – | – | radio_standards=Bluetooth Basic Rate, Bluetooth Enhanced Data Rate, Bluetooth Low Energy, Bluetooth Core v6.0, LE 2M PHY, LE Coded PHY | limited |
| [anritsu-mt8862a](equipment/anritsu/anritsu-mt8862a.json) | 계열 | radio_communication_tester |  | – | – | bandwidth_Hz=≤320000000; rf_output_level_dBm=-120–0; radio_standards=IEEE 802.11a/b/g/n/ac/ax/be | limited |
| [anritsu-mt8870a](equipment/anritsu/anritsu-mt8870a.json) | 계열 | radio_communication_tester |  | – | – | frequency_Hz=10000000–7300000000; bandwidth_Hz=≤200000000; rf_output_level_dBm=-130–0; channels=≤4; rf_port_count=≤24; radio_standards=5G NR Sub-6 GHz, LTE/LTE- | catalog |
| [anritsu-shockline-ms46522b](equipment/anritsu/anritsu-shockline-ms46522b.json) | 계열 | network_lcr_analyzer |  | – | – | frequency_Hz=50000–92000000000; rf_port_count=2 | limited |
| [anritsu-vectorstar-ms4640b](equipment/anritsu/anritsu-vectorstar-ms4640b.json) | 계열 | network_lcr_analyzer |  | – | – | frequency_Hz=70000–70000000000; rf_port_count=2; dynamic_range_dB=≤142; rf_output_level_dBm=≤14 | limited |

## Anton Paar (`anton-paar`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [anton-paar-litesizer](equipment/anton-paar/anton-paar-litesizer.json) | 계열 | particle_size_analyzer | particle_size | – | 0.0–90.0 |  | catalog |
| [anton-paar-mcr-measuring-cells](equipment/anton-paar/anton-paar-mcr-measuring-cells.json) | **부속** | accessory | rheology_rotational | – | -40–300 | pressure_bar=≤1000; shear_rate_1_s=≤3000; heating_rate_K_min=≤90 | limited |
| [anton-paar-mcr-rheometer](equipment/anton-paar/anton-paar-mcr-rheometer.json) | 계열 | rotational_rheometer | rheology_rotational, dma, friction_wear_tribo, tensile, compression, flexure | – | -170–1730 (부속) | torque_mNm=2e-07–300; rotation_rpm=≤6000; frequency_Hz=–; humidity_pct=5–95; viscosity_Pa_s=0.001–100000000 | limited |
| [anton-paar-mcr-temperature-and-humidity-options](equipment/anton-paar/anton-paar-mcr-temperature-and-humidity-options.json) | **부속** | environmental_chamber | rheology_rotational, dma, damp_heat | – | -170–180 | humidity_pct=5–95; cooling_rate_K_min=≤70 | limited |
| [anton-paar-nanoindentation](equipment/anton-paar/anton-paar-nanoindentation.json) | 계열 | instrumented_indentation | instrumented_indentation, friction_wear_tribo | – | ≤800 | indentation_force_mN=0.1–500 | limited |
| [anton-paar-step-platform-modules](equipment/anton-paar/anton-paar-step-platform-modules.json) | **부속** | accessory | instrumented_indentation, scratch_pencil_hardness, friction_wear_tribo | – | 23–450 | friction_force_mN=≤200000; stage_travel_mm=≤0.1 | limited |
| [anton-paar-tribometers](equipment/anton-paar/anton-paar-tribometers.json) | 계열 | tribometer | friction_wear_tribo | – | -160–1000 | force_N=5e-06–70; humidity_pct=5–95; rotation_rpm=1e-06–3000; sliding_speed_m_s=1e-08–3.3; frequency_Hz=0.01–10; torque_mNm=≤450 | catalog |
| [anton-paar-tribometers-materialtwin](equipment/anton-paar/anton-paar-tribometers-materialtwin.json) | 계열 (보탬→anton-paar-tribometers) | tribometer | friction_wear_tribo | – | – |  | catalog |

## Arbin Instruments (`arbin`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [arbin-evts](equipment/arbin/arbin-evts.json) | 계열 | battery_cycler | battery_cycle_life | – | – | power_kW=≤450; regenerative_efficiency_pct=≥90; control_period_ms=≥100 | catalog |
| [arbin-lbt-cell-tester](equipment/arbin/arbin-lbt-cell-tester.json) | 계열 | battery_cycler | battery_cycle_life | – | – | voltage_V=-5–10; current_A=0.0001–10; channel_power_W=≤100 | catalog |
| [arbin-mstat](equipment/arbin/arbin-mstat.json) | 계열 | battery_cycler | battery_cycle_life | – | – | voltage_V=-5–5; current_A=0.001–5; channels=4–64 | catalog |

## ATEQ (`ateq`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [ateq-f620](equipment/ateq/ateq-f620.json) | 기종 | pressure_decay_leak_tester | leak_rate | – | – | differential_pressure_Pa=≤5000; pressure_resolution_Pa=≥0.1; test_pressure_bar=≤3 | catalog |

## Atlas Material Testing Technology (`atlas`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [atlas-ci-series](equipment/atlas/atlas-ci-series.json) | 계열 | weathering_tester | accelerated_weathering | – | – | irradiance_control_nm=340, 420, 300-400; exposure_area_cm2=2188–11000; lamp_power_W=4500–12000 | limited |
| [atlas-suntest](equipment/atlas/atlas-suntest.json) | 계열 | weathering_tester | accelerated_weathering | – | – | irradiance_W_m2=30–80; black_panel_temperature_degC=25–100; exposure_area_cm2=560–3000 | catalog |
| [atlas-uvtest](equipment/atlas/atlas-uvtest.json) | 기종 | weathering_tester | accelerated_weathering | – | – | irradiance_control_nm=340, 313, 351; black_panel_temperature_degC=35–80 | catalog |
| [atlas-xenotest](equipment/atlas/atlas-xenotest.json) | 계열 | weathering_tester | accelerated_weathering | – | ≤70 | irradiance_control_nm=300-400; irradiance_W_m2=≤180; black_panel_temperature_degC=≤130; humidity_pct=10–75; exposure_area_cm2=1320–4000 | limited |

## Audio Precision (`audio-precision`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [audio-precision-apx511-b-series](equipment/audio-precision/audio-precision-apx511-b-series.json) | 기종 | audio_analyzer | audio_performance | – | – | frequency_Hz=100–20000; power_W=≤4; residual_thd_n_dB=≤-80; residual_noise_uV=≤1.3 | limited |
| [audio-precision-apx515-b-series](equipment/audio-precision/audio-precision-apx515-b-series.json) | 기종 | audio_analyzer | audio_performance | – | – | frequency_Hz=2–80100; analog_output_voltage_Vrms=≤16.0; residual_thd_n_dB=≤-102; bandwidth_Hz=≥90000; residual_noise_uV=≤1.4; digital_sample_rate_Hz=27000–20000 | limited |
| [audio-precision-apx516-b-series](equipment/audio-precision/audio-precision-apx516-b-series.json) | 기종 | audio_analyzer | audio_performance | – | – | frequency_Hz=2–80100; analog_output_voltage_Vrms=≤14.4; residual_thd_n_dB=≤-100; bandwidth_Hz=≥90000; residual_noise_uV=≤2.0; channels=2 | limited |
| [audio-precision-apx517-b-series](equipment/audio-precision/audio-precision-apx517-b-series.json) | 기종 | audio_analyzer | audio_performance | – | – | analog_output_voltage_Vrms=≤17; power_W=≤35; residual_thd_n_dB=≤-98; digital_sample_rate_Hz=≤192000 | limited |
| [audio-precision-apx52x-b-series](equipment/audio-precision/audio-precision-apx52x-b-series.json) | 계열 | audio_analyzer | audio_performance | – | – | frequency_Hz=0.1–80100; analog_output_voltage_Vrms=≤21.21; residual_thd_n_dB=≤-105; bandwidth_Hz=90000–1000000; residual_noise_uV=≤1.3; digital_sample_rate_Hz=2 | limited |
| [audio-precision-apx555](equipment/audio-precision/audio-precision-apx555.json) | 기종 | audio_analyzer | audio_performance | – | – | bandwidth_Hz=≤1000000; residual_thd_n_dB=≤-120; analog_output_voltage_Vrms=≤26; digital_sample_rate_Hz=≤432000; channels=2 | catalog |
| [audio-precision-apx58x-b-series](equipment/audio-precision/audio-precision-apx58x-b-series.json) | 계열 | audio_analyzer | audio_performance | – | – | frequency_Hz=5–80100; analog_output_voltage_Vrms=≤26.66; residual_thd_n_dB=≤-103; bandwidth_Hz=≤90000; residual_noise_uV=≤1.3; digital_sample_rate_Hz=27000–2000 | limited |

## Bareiss (`bareiss`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [bareiss-digi-test-ii](equipment/bareiss/bareiss-digi-test-ii.json) | 기종 | shore_irhd_hardness | hardness_shore, hardness_irhd | – | – | hardness_scales=Shore A, Micro Shore A, Shore A0, Shore B, Shore 0, Shore C, Shore D, Micro Shore D; specimen_thickness_mm=0.5–6 | catalog |
| [bareiss-positioning-devices-centrofix-rotofix-barofix](equipment/bareiss/bareiss-positioning-devices-centrofix-rotofix-barofix.json) | **부속** | accessory | hardness_shore, hardness_irhd | – | – | specimen_thickness_mm=≥0.7 | limited |
| [bareiss-punching-presses-sp-1000-ii-sp-4000-ii](equipment/bareiss/bareiss-punching-presses-sp-1000-ii-sp-4000-ii.json) | **부속** | specimen_preparation | tensile, tear, hardness_shore | ≤5 | – | specimen_thickness_mm=≤24; throat_depth_mm=≤60 | limited |
| [bareiss-reference-blocks-and-control-devices](equipment/bareiss/bareiss-reference-blocks-and-control-devices.json) | **부속** | accessory | hardness_shore, hardness_irhd | – | – | hardness_shore_a=20–80 | limited |
| [bareiss-test-stands-bs-61-ii-bsa-ii](equipment/bareiss/bareiss-test-stands-bs-61-ii-bsa-ii.json) | **부속** | accessory | hardness_shore | – | – | specimen_thickness_mm=≥6 | limited |

## BINDER GmbH (`binder`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [binder-kbf](equipment/binder/binder-kbf.json) | 계열 | climatic_chamber | damp_heat | – | -20–100 | humidity_pct=10–98; chamber_volume_L=127–1610 | limited |
| [binder-kbf-s-eco](equipment/binder/binder-kbf-s-eco.json) | 계열 | climatic_chamber | damp_heat | – | 0–70 | humidity_pct=10–80; chamber_volume_L=247–1020 | limited |
| [binder-kmf](equipment/binder/binder-kmf.json) | 계열 | climatic_chamber | damp_heat | – | -10–100 | humidity_pct=10–98; chamber_volume_L=102–700 | limited |
| [binder-mkf](equipment/binder/binder-mkf.json) | 계열 | climatic_chamber | damp_heat, temperature_cycling | – | -40–180 | humidity_pct=10–98; chamber_volume_L=60–991; heating_rate_K_min=4.8–5.5; cooling_rate_K_min=4.5–5.0; temperature_fluctuation_degC=0.1–0.6 | limited |

## Brookfield AMETEK (`brookfield-ametek`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [brookfield-dv3t](equipment/brookfield-ametek/brookfield-dv3t.json) | 계열 | viscometer | rheology_rotational | – | – |  | catalog |

## Brüel & Kjær (HBK) (`bruel-kjaer`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [bruel-kjaer-hats-5128](equipment/bruel-kjaer/bruel-kjaer-hats-5128.json) | 계열 | head_torso_simulator | audio_performance | – | – | frequency_Hz=20–20000; ear_simulators=1, 2 | catalog |

## Bruker (Hysitron) (`bruker`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [bruker-avance-ssnmr](equipment/bruker/bruker-avance-ssnmr.json) | 기종 | nmr_spectrometer | composition_analysis | – | – |  | limited |
| [bruker-contourx-200](equipment/bruker/bruker-contourx-200.json) | 기종 | optical_profilometer | surface_topography | – | – | scan_range_mm=≤10; vertical_resolution_nm=≤0.01; sample_thickness_mm=≤100; stage_size_mm=≤150; repeatability_pct=≤0.1 | catalog |
| [bruker-d8-advance](equipment/bruker/bruker-d8-advance.json) | 기종 | xray_diffractometer | crystal_structure_analysis, dsc, coating_thickness | – | -193.0–2300.0 |  | catalog |
| [bruker-dektakxt](equipment/bruker/bruker-dektakxt.json) | 기종 | optical_profilometer | surface_topography, coating_thickness | – | – | scan_length_mm=≤55; vertical_range_mm=≤1; stylus_force_mg=0.03–15; sample_thickness_mm=≤50; stylus_radius_um=2 | limited |
| [bruker-dektakxt-materialtwin](equipment/bruker/bruker-dektakxt-materialtwin.json) | 계열 (보탬→bruker-dektakxt) | optical_profilometer | surface_topography, coating_thickness | – | – |  | limited |
| [bruker-hysitron-pi-95-picoindenter](equipment/bruker/bruker-hysitron-pi-95-picoindenter.json) | 계열 | nanoindenter | instrumented_indentation, compression | – | – | force_N=≤0.0015; displacement_um=≤5; frequency_Hz=110–1800 | catalog |
| [bruker-hysitron-ti-950-triboindenter](equipment/bruker/bruker-hysitron-ti-950-triboindenter.json) | 계열 | nanoindenter | instrumented_indentation, friction_wear_tribo, surface_topography | – | – | indentation_force_mN=–; position_resolution_nm=≤0.02; stage_travel_mm=≤250; data_rate_Hz=≤30000; field_of_view_mm=0.028–0.625; magnification=10–220 | catalog |
| [bruker-hysitron-ts-75-triboscope](equipment/bruker/bruker-hysitron-ts-75-triboscope.json) | **부속** | nanoindenter | instrumented_indentation, surface_topography, friction_wear_tribo | – | – | position_resolution_nm=≤0.0004; indentation_force_mN=– | catalog |
| [bruker-umt-tribolab](equipment/bruker/bruker-umt-tribolab.json) | 기종 | tribometer | friction_wear_tribo | – | -40–1200 (부속) | force_N=0.001–2000; rotation_rpm=≤5000; frequency_Hz=≤60; torque_Nm=≤5; humidity_pct=5–85; data_rate_Hz=≤200000 | limited |
| [bruker-vertex-ftir](equipment/bruker/bruker-vertex-ftir.json) | 계열 | composition_spectrometer | composition_analysis | – | ≤-263.15 |  | limited |

## Buehler (Wilson) (`buehler`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [buehler-wilson-hardness](equipment/buehler/buehler-wilson-hardness.json) | 계열 | hardness | hardness_rockwell, hardness_vickers, hardness_brinell, hardness_knoop | – | – | test_load_kgf=– | limited |
| [buehler-wilson-uh4000](equipment/buehler/buehler-wilson-uh4000.json) | 계열 | universal_hardness | hardness_brinell, hardness_vickers, hardness_rockwell, hardness_knoop | – | – | test_load_kgf=0.5–750; hardness_scales=HV 0.5 – HV 100, HBW 1/1 – HBW 10/3000 (UH4750: HBW 10/750 max), HRA–HRV, HR15/30/45 N/T, HK, ball indentation (plastics) | catalog |
| [buehler-wilson-vh3300](equipment/buehler/buehler-wilson-vh3300.json) | 계열 | vickers_knoop_hardness | hardness_vickers, hardness_knoop | – | – | test_load_gf=10–50000; hardness_scales=HV, HK; specimen_height_mm=≤215; stage_travel_mm=180×180, 300×180 | catalog |
| [buehler-wilson-vh3300-materialtwin](equipment/buehler/buehler-wilson-vh3300-materialtwin.json) | 계열 (보탬→buehler-wilson-vh3300) | vickers_knoop_hardness | hardness_vickers, hardness_knoop | – | – |  | catalog |

## Chroma ATE (`chroma`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [chroma-17011-battery-cell-tester](equipment/chroma/chroma-17011-battery-cell-tester.json) | 계열 | battery_cycler | battery_cycle_life | – | – | voltage_V=0–6; current_A=≤1200; current_response_time_us=≤100 | catalog |
| [chroma-19032-safety-analyzer](equipment/chroma/chroma-19032-safety-analyzer.json) | 계열 | hipot_safety_analyzer | dielectric_withstand, insulation_resistance, ground_bond | – | – | ac_withstand_voltage_kV=0.05–5.0; dc_withstand_voltage_kV=0.05–6.0; cutoff_current_A=≤0.1; insulation_test_voltage_kV=0.05–3.0; insulation_resistance_ohm=100000 | catalog |
| [chroma-61500-ac-source](equipment/chroma/chroma-61500-ac-source.json) | 계열 | ac_power_source | power_consumption, surge_eft_immunity | – | – | output_power_VA=500–4000; output_voltage_V=0–300; crest_factor=≤6; harmonic_order=≤40; phases=1, 3 | catalog |
| [chroma-63200-dc-load](equipment/chroma/chroma-63200-dc-load.json) | 계열 | electronic_load | power_consumption, battery_cycle_life | – | – | voltage_V=0–1000; current_A=0–1000; power_W=260–15600; dynamic_frequency_Hz=≤20000; slew_rate_A_us=≤41.6; min_rise_time_us=20–150 | catalog |

## Comet Yxlon (`comet-yxlon`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [comet-yxlon-cheetah-evo](equipment/comet-yxlon/comet-yxlon-cheetah-evo.json) | 계열 | xray_inspection | xray_void_inspection | – | – | tube_voltage_kV=20–160; pixel_pitch_um=127; sample_size_mm=≤800; inspection_area_mm=≤460; sample_weight_kg=≤20; oblique_view_angle_deg=≤70 | limited |
| [comet-yxlon-cougar-evo](equipment/comet-yxlon/comet-yxlon-cougar-evo.json) | 계열 | xray_inspection | xray_void_inspection | – | – | tube_voltage_kV=20–160; pixel_pitch_um=127; inspection_area_mm=≤310; sample_size_mm=≤550; oblique_view_angle_deg=≤70 | limited |
| [comet-yxlon-ff-ct](equipment/comet-yxlon/comet-yxlon-ff-ct.json) | 계열 | xray_inspection | xray_void_inspection | – | – | tube_voltage_kV=160, 190, 225, 300, 450, 600; tube_power_W=≤320; feature_recognition_um=≥0.15; specimen_diameter_mm=≤1800; specimen_height_mm=≤3000; sample_weig | limited |
| [comet-yxlon-ux](equipment/comet-yxlon/comet-yxlon-ux.json) | 계열 | xray_inspection | xray_void_inspection | – | – | tube_voltage_kV=160–450; pixel_pitch_um=139, 179; voxel_size_um=≥55; sample_weight_kg=≤100; specimen_diameter_mm=≤600; specimen_height_mm=≤850; inspection_area_ | limited |

## Copper Mountain Technologies (`copper-mountain`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [copper-mountain-50-ohm-vna](equipment/copper-mountain/copper-mountain-50-ohm-vna.json) | 계열 | network_lcr_analyzer |  | – | – | frequency_Hz=9000–22000000000; rf_port_count=1, 2, 4, 6, 8, 10, 12, 14; dynamic_range_dB=≤140 | limited |

## Correlated Solutions, Inc. (`correlated-solutions`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [correlated-solutions-vic-2d](equipment/correlated-solutions/correlated-solutions-vic-2d.json) | 계열 | dic_strain_measurement | tensile, compression, fatigue | – | – | strain_range_pct=0.005–2000; detector_megapixels=1–45; frame_rate_fps=15–76000; max_frame_rate_fps=≤20000000 | catalog |
| [correlated-solutions-vic-3d](equipment/correlated-solutions/correlated-solutions-vic-3d.json) | 계열 | dic_strain_measurement | tensile, compression, fatigue | – | – | strain_range_pct=0.005–2000; strain_resolution_microstrain=≥5; data_rate_Hz=≤20000000; detector_megapixels=1–45; field_of_view_mm=≥0.7; specimen_size_mm=1–10000 | catalog |
| [correlated-solutions-vic-volume](equipment/correlated-solutions/correlated-solutions-vic-volume.json) | software | dic_strain_measurement | compression, tensile | – | – |  | catalog |

## Crystal Instruments (`crystal-instruments`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [crystal-instruments-spider-vibration-controllers](equipment/crystal-instruments/crystal-instruments-spider-vibration-controllers.json) | 계열 | mechanical_dynamics | vibration_sine_random, mechanical_shock | – | – | channels=4–1024; dynamic_range_dB=160–160; adc_resolution_bit=24; data_rate_Hz=≤256000 | limited |

## C.S.C. Force Measurement (`cscforce`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [cscforce-wt-205m](equipment/cscforce/cscforce-wt-205m.json) | 기종 | crimp_pull_tester | crimp_pull_strength | – | – | pull_force_N=≤1000; wire_diameter_mm=≤6.3 | catalog |

## Cincinnati Sub-Zero (CSZ) (`csz`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [csz-ca-altitude-chambers](equipment/csz/csz-ca-altitude-chambers.json) | 계열 | altitude_chamber | altitude_low_pressure, temperature_cycling, damp_heat | – | -68–180 | chamber_pressure_kPa=≥1.09; altitude_m=≤30480; humidity_pct=10–95; chamber_volume_L=227–1812 | catalog |
| [csz-thermal-shock](equipment/csz/csz-thermal-shock.json) | 계열 | thermal_shock_chamber | thermal_shock, temperature_cycling | – | – | high_temp_degC=≤210; low_temp_degC=≥-75; chamber_volume_L=30–1274 | limited |
| [csz-z-plus-chambers](equipment/csz/csz-z-plus-chambers.json) | 계열 | climatic_chamber | damp_heat, temperature_cycling | – | – | chamber_volume_L=227–2718 | limited |

## Daekyung Tech (대경테크) (`daekyung-tech`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [daekyung-tech-dtb-brinell](equipment/daekyung-tech/daekyung-tech-dtb-brinell.json) | 계열 | brinell_hardness | hardness_brinell | – | – | test_load_kgf=500, 750, 1000, 1500, 2000, 2500, 3000; specimen_height_mm=≤175; hardness_scales=HBW; weight_kg=≤135 | limited |

## Dantec Dynamics A/S (`dantec-dynamics`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [dantec-dynamics-dic-systems](equipment/dantec-dynamics/dantec-dynamics-dic-systems.json) | 계열 | dic_strain_measurement | tensile, compression, flexure, fatigue, fracture_toughness | – | -80–400 (부속) | data_rate_Hz=≤40000; detector_megapixels=1–24.4; field_of_view_mm=0.1–1500; strain_resolution_microstrain=10–15 | limited |

## Data Physics Corporation (`data-physics`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [data-physics-signalforce-air-cooled-shakers](equipment/data-physics/data-physics-signalforce-air-cooled-shakers.json) | 계열 | vibration_shaker | vibration_sine_random | 0.009–66.7 | – | force_random_kN=0.003–66.7 | limited |
| [data-physics-signalforce-water-cooled-shakers](equipment/data-physics/data-physics-signalforce-water-cooled-shakers.json) | 계열 | vibration_shaker | vibration_sine_random | 71–222 | – | force_random_kN=71–200; velocity_m_s=≤2; displacement_mm=≤76.2; payload_kg=≤1365 | limited |

## DeFelsko (`defelsko`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [defelsko-positector-6000](equipment/defelsko/defelsko-positector-6000.json) | 계열 | coating_surface_test | coating_thickness | – | – | coating_thickness_um=0–63500 | limited |
| [defelsko-positest-at](equipment/defelsko/defelsko-positest-at.json) | 계열 | adhesion_tester | coating_adhesion | – | – | pull_off_strength_MPa=0.1–96; dolly_diameter_mm=10, 14, 20, 50 | limited |
| [defelsko-positest-pt](equipment/defelsko/defelsko-positest-pt.json) | 기종 | scratch_hardness_tester | scratch_pencil_hardness | – | – | pencil_hardness_grade=– | limited |

## Ducom Instruments (`ducom`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [ducom-lubricant-testers](equipment/ducom/ducom-lubricant-testers.json) | 계열 | tribometer | friction_wear_tribo | – | ≤400 | force_N=100–10000; rotation_rpm=300–3000; friction_force_mN=≤200000; torque_Nm=≤16; frequency_Hz=10–200; stroke_mm=0.02–2.0 | limited |
| [ducom-tribometers](equipment/ducom/ducom-tribometers.json) | 계열 | tribometer | friction_wear_tribo | – | -120–1200 (부속) | force_N=0.25–200; rotation_rpm=0.1–5000 | limited |

## Elcometer (`elcometer`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [elcometer-106](equipment/elcometer/elcometer-106.json) | 계열 | adhesion_tester | coating_adhesion | – | – | pull_off_strength_MPa=0.05–22; dolly_diameter_mm=20 | limited |
| [elcometer-1720](equipment/elcometer/elcometer-1720.json) | 기종 | abrasion_tester | abrasion | – | – | stroke_mm=10–300; cycle_rate_cpm=10–65 | limited |
| [elcometer-456](equipment/elcometer/elcometer-456.json) | 계열 | coating_surface_test | coating_thickness | – | – | coating_thickness_um=0–31000; operating_temperature_degC=-10–50 | limited |
| [elcometer-506](equipment/elcometer/elcometer-506.json) | 기종 | adhesion_tester | coating_adhesion | – | – | pull_off_strength_MPa=0.3–50; dolly_diameter_mm=14.2, 20, 50 | limited |
| [elcometer-510](equipment/elcometer/elcometer-510.json) | 계열 | adhesion_tester | coating_adhesion | – | – | pull_off_strength_MPa=0.3–100; dolly_diameter_mm=10, 14.2, 20, 50; pull_rate_MPa_s=0.02–5.6 | catalog |
| [elcometer-cross-hatch-adhesion-testers](equipment/elcometer/elcometer-cross-hatch-adhesion-testers.json) | 계열 | adhesion_tester | coating_adhesion | – | – | cut_spacing_mm=1, 1.5, 2, 3; coating_thickness_um=0–250; cross_cut_squares=100 | limited |
| [elcometer-pencil-scratch-hardness](equipment/elcometer/elcometer-pencil-scratch-hardness.json) | 계열 | scratch_hardness_tester | scratch_pencil_hardness | – | – | pencil_hardness_grade=6B, 5B, 4B, 3B, 2B, B, HB, F; pencil_angle_deg=45; pencil_load_g=764.8; load_N=0–30 | limited |

## EM TEST (AMETEK CTS) (`em-test`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [em-test-esd-simulators](equipment/em-test/em-test-esd-simulators.json) | 계열 | esd_simulator | esd_immunity | – | – | esd_voltage_kV=0.2–30; discharge_mode=contact, air; frequency_Hz=0.5–25; polarity=positive, negative, alternating | catalog |

## EMCO-TEST (`emco-test`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [emco-test-durajet-g5](equipment/emco-test/emco-test-durajet-g5.json) | 계열 | rockwell_hardness | hardness_rockwell, hardness_vickers, hardness_brinell | – | – | test_load_kgf=1–250; hardness_scales=HRA–HRV, HR15/30/45 N/T/W/X/Y, HR 2/10, 2/20, 2/120, HVT 5–100, HBT 1/5 – 2.5/187.5, 5/250, plastics 49–961 N; specimen_hei | catalog |
| [emco-test-duravision-g5](equipment/emco-test/emco-test-duravision-g5.json) | 계열 | universal_hardness | hardness_brinell, hardness_vickers, hardness_rockwell, hardness_knoop | – | – | test_load_kgf=0.3–3000; hardness_scales=HBW 1/1 – 10/3000, HV 0.3 – HV 150, HK 0.3 – HK 2, HRA–HRV, HR15/30/45 N/T/W/X/Y, plastics 49–961 N, carbon DIN 51917; s | catalog |
| [emco-test-ecos-workflow-software-modules](equipment/emco-test/emco-test-ecos-workflow-software-modules.json) | software | accessory | hardness_rockwell, hardness_brinell, hardness_vickers, hardness_knoop | – | – |  | limited |
| [emco-test-hardness-tester-accessories](equipment/emco-test/emco-test-hardness-tester-accessories.json) | **부속** | accessory | hardness_rockwell, hardness_brinell, hardness_vickers, hardness_knoop | – | – | magnification=2.5–100 | limited |

## Epsilon Technology Corp. (`epsilon`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [epsilon-3542-3442-axial-extensometers](equipment/epsilon/epsilon-3542-3442-axial-extensometers.json) | **센서** | extensometer | tensile, compression, fatigue | – | -270–200 | gauge_length_mm=3–80; displacement_mm=–; weight_kg=≤0.03 | catalog |

## ERICHSEN (`erichsen`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [erichsen-430p-scratch-tester](equipment/erichsen/erichsen-430p-scratch-tester.json) | 기종 | scratch_hardness_tester | scratch_pencil_hardness, coating_adhesion | – | – | load_N=–; scratch_speed=– | limited |

## ESPEC (`espec`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [espec-agree-et](equipment/espec/espec-agree-et.json) | 기종 | climatic_chamber | temperature_cycling, damp_heat | – | – |  | limited |
| [espec-ar-series](equipment/espec/espec-ar-series.json) | 계열 | climatic_chamber | damp_heat, temperature_cycling | – | – |  | limited |
| [espec-criterion](equipment/espec/espec-criterion.json) | 계열 | climatic_chamber | damp_heat, temperature_cycling | – | – |  | limited |
| [espec-ehs-tpc-hast](equipment/espec/espec-ehs-tpc-hast.json) | 기종 | hast_chamber | hast | – | – |  | limited |
| [espec-er-rain-spray-chamber](equipment/espec/espec-er-rain-spray-chamber.json) | 계열 | water_ingress_tester | water_ingress | – | -20–150 (부속) | ipx_levels=–; chamber_volume_L=≤1000; humidity_pct=20–95; water_temperature_degC=5–20 | limited |
| [espec-ev-altitude-chambers](equipment/espec/espec-ev-altitude-chambers.json) | 계열 | altitude_chamber | altitude_low_pressure, temperature_cycling, damp_heat | – | -65–150 | altitude_m=≤30480; humidity_pct=10–95; heating_rate_K_min=1–8; cooling_rate_K_min=1–8; chamber_volume_L=200–1812 | limited |
| [espec-fd-series](equipment/espec/espec-fd-series.json) | 계열 | climatic_chamber | damp_heat, temperature_cycling | – | -70–180 | humidity_pct=20–95; chamber_volume_L=1800–11000; heating_rate_K_min=≥3; cooling_rate_K_min=≥3 | limited |
| [espec-hr-high-rate](equipment/espec/espec-hr-high-rate.json) | 계열 | climatic_chamber | temperature_cycling, damp_heat | – | -70–180 | humidity_pct=20–98; heating_rate_K_min=20–25; cooling_rate_K_min=20–25; chamber_volume_L=357–1800 | limited |
| [espec-industrial-ovens](equipment/espec/espec-industrial-ovens.json) | 기종 | industrial_oven | damp_heat | – | – |  | limited |
| [espec-lab-series](equipment/espec/espec-lab-series.json) | 기종 | climatic_chamber | damp_heat | – | – |  | limited |
| [espec-ls-constant-climate](equipment/espec/espec-ls-constant-climate.json) | 계열 | climatic_chamber | damp_heat | – | -20–85 | humidity_pct=40–95 | limited |
| [espec-mc-ultra-low](equipment/espec/espec-mc-ultra-low.json) | 계열 | climatic_chamber | temperature_cycling | – | -85–180 |  | limited |
| [espec-platinous-chambers](equipment/espec/espec-platinous-chambers.json) | 계열 | climatic_chamber | damp_heat, temperature_cycling | – | -70–200 | humidity_pct=5–98; heating_rate_K_min=3–6; cooling_rate_K_min=1–5; chamber_volume_L=225–900 | catalog |
| [espec-platinous-chambers-materialtwin](equipment/espec/espec-platinous-chambers-materialtwin.json) | 계열 (보탬→espec-platinous-chambers) | climatic_chamber | damp_heat, temperature_cycling | – | – |  | limited |
| [espec-qualmark-halt-hass](equipment/espec/espec-qualmark-halt-hass.json) | 계열 | halt_hass_chamber | halt_hass, vibration_sine_random, temperature_cycling, thermal_shock | – | -100–250 | heating_rate_K_min=≤70; acceleration_gRMS=5–75; table_size_mm=457–2794; payload_kg=45–907 | catalog |
| [espec-sh-benchtop-models](equipment/espec/espec-sh-benchtop-models.json) | 계열 (보탬→espec-su-sh-benchtop) | climatic_chamber | damp_heat | – | -60–150 | humidity_pct=30–95 | limited |
| [espec-su-sh-benchtop](equipment/espec/espec-su-sh-benchtop.json) | 기종 | climatic_chamber | damp_heat | – | – |  | limited |
| [espec-tsa-d-humidity](equipment/espec/espec-tsa-d-humidity.json) | 계열 | thermal_shock_chamber | thermal_shock, damp_heat | – | – | high_temp_degC=70–150; low_temp_degC=-70–10; humidity_fluctuation_pct=≤5 | limited |
| [espec-tsa-large-thermal-shock](equipment/espec/espec-tsa-large-thermal-shock.json) | 계열 | thermal_shock_chamber | thermal_shock, temperature_cycling | – | – | high_temp_degC=60–180; low_temp_degC=-60–0; chamber_volume_L=600–12000 | limited |
| [espec-tsa-thermal-shock](equipment/espec/espec-tsa-thermal-shock.json) | 계열 | thermal_shock_chamber | thermal_shock, temperature_cycling | – | -70–200 | preheat_limit_degC=≤205; precool_limit_degC=≥-77; temperature_fluctuation_degC=≤0.5; chamber_volume_L=40.8–299.2; load_kg=30–50; ambient_degC=0–40 | catalog |
| [espec-tsa-thermal-shock-materialtwin](equipment/espec/espec-tsa-thermal-shock-materialtwin.json) | 계열 (보탬→espec-tsa-thermal-shock) | thermal_shock_chamber | thermal_shock, temperature_cycling | – | – |  | limited |
| [espec-tsb-liquid-thermal-shock](equipment/espec/espec-tsb-liquid-thermal-shock.json) | 기종 | thermal_shock_chamber | thermal_shock | – | – |  | limited |
| [espec-tse-11-a](equipment/espec/espec-tse-11-a.json) | 기종 | thermal_shock_chamber | thermal_shock | – | – |  | limited |
| [espec-tsh-haats](equipment/espec/espec-tsh-haats.json) | 기종 | thermal_shock_chamber | thermal_shock, temperature_cycling | – | – | high_temp_degC=60–200; low_temp_degC=-70–0; recovery_time_min=≤3 | limited |
| [espec-walk-in-chambers](equipment/espec/espec-walk-in-chambers.json) | 계열 | climatic_chamber | damp_heat, temperature_cycling | – | -70–150 | humidity_pct=10–95; heating_rate_K_min=1–4; cooling_rate_K_min=0.4–3 | catalog |
| [espec-walk-in-chambers-materialtwin](equipment/espec/espec-walk-in-chambers-materialtwin.json) | 계열 (보탬→espec-walk-in-chambers) | climatic_chamber | damp_heat, temperature_cycling | – | – |  | limited |

## ETS-Lindgren (`ets-lindgren`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [ets-lindgren-shielding](equipment/ets-lindgren/ets-lindgren-shielding.json) | 계열 | shielded_enclosure | shielding_effectiveness, emi_emission | – | – | frequency_Hz=14000–1000000000; insertion_gain=– | limited |
| [ets-lindgren-smart-reverberation-chamber](equipment/ets-lindgren/ets-lindgren-smart-reverberation-chamber.json) | 계열 | reverberation_chamber | emi_emission, shielding_effectiveness, esd_immunity, surge_eft_immunity | – | – | frequency_Hz=80000000–40000000000; chamber_volume_L=– | limited |

## Evident Corporation (`evident`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [evident-bx53m](equipment/evident/evident-bx53m.json) | 계열 | optical_microscope | microscopy | – | – | specimen_height_mm=0–105; stage_travel_mm=≤150; magnification=12.5–1500 | catalog |
| [evident-dsx-digital-microscopes](equipment/evident/evident-dsx-digital-microscopes.json) | 계열 | optical_microscope | microscopy | – | – | magnification=20.9–8220; zoom_ratio=10; working_distance_mm=0.35–66.1; detector_megapixels=2.35–12.37; data_rate_Hz=≤60; stage_travel_mm=≤200; tilt_angle_deg=-9 | limited |
| [evident-lext-ols5100](equipment/evident/evident-lext-ols5100.json) | 계열 | optical_profilometer | surface_topography, microscopy | – | – | laser_wavelength_nm=405; magnification=54–17280; field_of_view_mm=0.016–5.12; vertical_resolution_nm=≤0.5; stage_travel_mm=≤300; specimen_height_mm=37–210; work | catalog |
| [evident-mx63-wafer-inspection-microscopes](equipment/evident/evident-mx63-wafer-inspection-microscopes.json) | 계열 | optical_microscope | microscopy | – | – | wafer_size_mm=≤300; stage_travel_mm=≤356; specimen_mass_kg=≤15; magnification=12.5–1500 | catalog |
| [evident-szx-sz-stereo-microscopes](equipment/evident/evident-szx-sz-stereo-microscopes.json) | 계열 | optical_microscope | microscopy | – | – | zoom_ratio=5–16.4; magnification=3.5–336; working_distance_mm=20–171; optical_resolution_lp_mm=≤900 | limited |

## Exosens (`exosens`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [exosens-xenics-bobcat](equipment/exosens/exosens-xenics-bobcat.json) | 계열 | high_speed_swir_camera |  | – | – | resolution_pixels=81920–327680; wavelength_nm=500–1700; frame_rate_fps=100–400; pixel_pitch_um=20 | catalog |
| [exosens-xenics-cheetah](equipment/exosens/exosens-xenics-cheetah.json) | 계열 | high_speed_swir_camera |  | – | – | resolution_pixels=≤327680; wavelength_nm=500–1700; frame_rate_fps=111–1730; pixel_pitch_um=20; adc_resolution_bit=14 | catalog |

## Filmetrics (KLA) (`filmetrics`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [filmetrics-f54](equipment/filmetrics/filmetrics-f54.json) | 계열 | film_thickness_analyzer | coating_thickness | – | – |  | catalog |

## Teledyne FLIR (`flir`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [flir-a6750-series](equipment/flir/flir-a6750-series.json) | 계열 | thermal_imager | thermography | – | -20–350 | ir_resolution_pixels=≤327680; thermal_sensitivity_degC=0.022–0.027; wavelength_nm=1000–5000; frame_rate_fps=0.0015–125; min_exposure_time_s=≥4.8e-07 | limited |
| [flir-axxx-series](equipment/flir/flir-axxx-series.json) | 계열 | thermal_imager | thermography | – | -20–2000 | ir_resolution_pixels=76800–307200; wavelength_nm=7500–14000; frame_rate_fps=30 | limited |
| [flir-e-series](equipment/flir/flir-e-series.json) | 계열 | thermal_imager | thermography | – | -20–550 | ir_resolution_pixels=19200–76800; thermal_sensitivity_degC=0.04–0.1; wavelength_nm=7500–13000; frame_rate_fps=9 | limited |
| [flir-exx-series](equipment/flir/flir-exx-series.json) | 계열 | thermal_imager | thermography | – | -20–1500 | ir_resolution_pixels=76800–307200; thermal_sensitivity_degC=0.03–0.05; wavelength_nm=7500–14000; frame_rate_fps=30 | limited |
| [flir-t500-series](equipment/flir/flir-t500-series.json) | 계열 | thermal_imager | thermography | – | -20–1500 | ir_resolution_pixels=76800–307200; thermal_sensitivity_degC=0.03–0.05; wavelength_nm=7500–14000; frame_rate_fps=30 | limited |
| [flir-t660](equipment/flir/flir-t660.json) | 기종 | thermal_imager | thermography | – | ≤2000 | ir_resolution_pixels=≤307200; thermal_sensitivity_degC=≤0.04 | catalog |
| [flir-t800-series](equipment/flir/flir-t800-series.json) | 계열 | thermal_imager | thermography | – | -40–2000 | ir_resolution_pixels=≤307200; accuracy_degC=– | catalog |
| [flir-x-series-science](equipment/flir/flir-x-series-science.json) | 계열 | thermal_imager | thermography | – | -20–350 | ir_resolution_pixels=327680–1310720; thermal_sensitivity_degC=0.02–0.03; wavelength_nm=1500–5000; frame_rate_fps=181–1004 | limited |

## Fluke Corporation (`fluke`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [fluke-170-series](equipment/fluke/fluke-170-series.json) | 계열 | dmm_daq |  | – | – |  | limited |
| [fluke-287-289](equipment/fluke/fluke-287-289.json) | 계열 | dmm_daq |  | – | – |  | limited |
| [fluke-87v](equipment/fluke/fluke-87v.json) | 계열 | dmm_daq |  | – | – |  | limited |
| [fluke-8845a-8846a](equipment/fluke/fluke-8845a-8846a.json) | 계열 | dmm_daq |  | – | – | dmm_resolution_digits=6.5; voltage_V=0.1–1000; current_A=0.0001–10; resistance_ohm=100–100000000 | limited |
| [fluke-ti-pro-series](equipment/fluke/fluke-ti-pro-series.json) | 계열 | thermal_imager | thermography | – | -20–1500 | ir_resolution_pixels=43200–307200; thermal_sensitivity_degC=0.025–0.075; frame_rate_fps=9, 60 | limited |
| [fluke-tis-series](equipment/fluke/fluke-tis-series.json) | 계열 | thermal_imager | thermography | – | -20–550 | ir_resolution_pixels=10800–110592; thermal_sensitivity_degC=0.04–0.06; frame_rate_fps=9, 27, 30 | limited |
| [fluke-tix-expert-series](equipment/fluke/fluke-tix-expert-series.json) | 계열 | thermal_imager | thermography | – | -20–1000 | ir_resolution_pixels=≤307200; thermal_sensitivity_degC=0.05–0.075 | limited |

## Four Dimensions, Inc. (`four-dimensions`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [four-dimensions-four-point-probes](equipment/four-dimensions/four-dimensions-four-point-probes.json) | 계열 | electrical_property_tester | electrical_transport | – | – | surface_resistivity_ohm_sq=0.001–4000000000.0; wafer_size_mm=≤200; sample_size_mm=≤220 | limited |

## FUJIFILM Corporation (`fujifilm`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [fujifilm-prescale](equipment/fujifilm/fujifilm-prescale.json) | **센서** | force_pressure_sensor |  | – | – |  | limited |

## GÖTTFERT (`goettfert`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [goettfert-counter-pressure-viscosimeter](equipment/goettfert/goettfert-counter-pressure-viscosimeter.json) | 계열 | capillary_rheometer | rheology_capillary | – | ≤400 | pressure_bar=≤1200; piston_speed_mm_min=0.0024–2400 | catalog |
| [goettfert-pvt500](equipment/goettfert/goettfert-pvt500.json) | 계열 | dilatometer | dilatometry, thermal_conductivity | – | – | pressure_bar=≤2500; cooling_rate_K_min=≤30; bore_diameter_mm=9.5 | catalog |
| [goettfert-rheograph](equipment/goettfert/goettfert-rheograph.json) | 계열 | capillary_rheometer | rheology_capillary | 20–120 | ≤400 | pressure_bar=20–2500; piston_speed_mm_min=0.0024–2400; bore_diameter_mm=9.55, 12, 15, 20, 25, 30; weight_kg=270–650 | catalog |
| [goettfert-rheograph-25e](equipment/goettfert/goettfert-rheograph-25e.json) | 계열 | capillary_rheometer | rheology_capillary | ≤25 | 30–250 | piston_speed_mm_min=0.0024–2400; bore_diameter_mm=20 | catalog |
| [goettfert-rheograph-add-ons](equipment/goettfert/goettfert-rheograph-add-ons.json) | **부속** | accessory | rheology_capillary, thermal_conductivity, dilatometry | – | ≤450 | pressure_bar=≤1200; velocity_m_s=≤33.3; force_N=≤1 | catalog |
| [goettfert-rheograph-auto](equipment/goettfert/goettfert-rheograph-auto.json) | 계열 | capillary_rheometer | rheology_capillary | 25–50 | ≤400 | piston_speed_mm_min=0.0024–2400; bore_diameter_mm=12, 15 | catalog |
| [goettfert-tcr](equipment/goettfert/goettfert-tcr.json) | 계열 | capillary_rheometer | rheology_capillary | ≤75 | – | pressure_bar=≤1600 | catalog |

## GRAPHTEC IWATSU Test Instruments Co., Ltd. (Graphtec) (`graphtec`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [graphtec-gl-high-speed-loggers](equipment/graphtec/graphtec-gl-high-speed-loggers.json) | 계열 | dmm_daq |  | – | – | data_rate_Hz=≤1000000; channels=2–2000 | limited |
| [graphtec-midi-logger](equipment/graphtec/graphtec-midi-logger.json) | 계열 | dmm_daq |  | – | – | channels=10–200; data_interval_ms=≤10; voltage_V=0.02–100 | limited |

## GRAS Sound & Vibration (`gras`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [gras-46-measurement-microphone-sets](equipment/gras/gras-46-measurement-microphone-sets.json) | **센서** | acoustic_measurement |  | – | – | frequency_Hz=3.15–80000; sound_pressure_level_dB=17–174; mic_sensitivity_mV_Pa=0.8–50 | limited |
| [gras-headphone-test-fixtures](equipment/gras/gras-headphone-test-fixtures.json) | 계열 | acoustic_measurement | audio_performance | – | – | insertion_gain=50–65; frequency_Hz=≤50000; weight_kg=≤11.6 | catalog |
| [gras-kemar-45bb-45bc](equipment/gras/gras-kemar-45bb-45bc.json) | 계열 | head_torso_simulator | audio_performance | – | – | channels=1, 2; frequency_Hz=≤50000; weight_kg=≤11.45; operating_temperature_degC=-30–60 | limited |

## Good Will Instrument Co., Ltd. (GW Instek) (`gw-instek`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [gw-instek-lcr-8200](equipment/gw-instek/gw-instek-lcr-8200.json) | 계열 | network_lcr_analyzer |  | – | – | frequency_Hz=10–50000000 | limited |

## Haefely AG (`haefely`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [haefely-onyx](equipment/haefely/haefely-onyx.json) | 계열 | esd_simulator | esd_immunity | – | – | esd_voltage_kV=1–30; discharge_mode=contact, air; polarity=positive, negative; frequency_Hz=single, 0.1, 0.2, 0.5, 1, 2, 5, 10 | limited |

## Hamamatsu Photonics (`hamamatsu`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [hamamatsu-ingaas-cameras](equipment/hamamatsu/hamamatsu-ingaas-cameras.json) | 계열 | high_speed_swir_camera |  | – | – | resolution_pixels=≤1310720; wavelength_nm=400–1700; frame_rate_fps=7.2–216.6; pixel_pitch_um=5, 12.5, 20 | catalog |

## HBM (HBK – Hottinger Brüel & Kjær) (`hbm`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [hbm-c9c](equipment/hbm/hbm-c9c.json) | **센서** | force_pressure_sensor |  | 0.05–50 | – |  | catalog |
| [hbm-s2m](equipment/hbm/hbm-s2m.json) | **센서** | force_pressure_sensor |  | – | – | force_N=10–1000 | limited |
| [hbm-u10m](equipment/hbm/hbm-u10m.json) | **센서** | force_pressure_sensor |  | 1.25–2500 | – |  | limited |

## HEAD acoustics (`head-acoustics`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [head-acoustics-hms-ii-artificial-heads](equipment/head-acoustics/head-acoustics-hms-ii-artificial-heads.json) | 계열 | head_torso_simulator | audio_performance | – | – | frequency_Hz=3–20000; sound_pressure_level_dB=15.5–148; ear_simulators=0, 1, 2 | limited |
| [head-acoustics-hms-v](equipment/head-acoustics/head-acoustics-hms-v.json) | 기종 | head_torso_simulator |  | – | – | data_rate_Hz=32768, 44100, 48000, 51200, 88200, 96000, 102400, 192000; adc_resolution_bit=32 | limited |
| [head-acoustics-hsu-iii](equipment/head-acoustics/head-acoustics-hsu-iii.json) | 계열 | head_torso_simulator |  | – | – | sound_pressure_level_dB=6.5–135; dynamic_range_dB=106.5–119.5 | limited |
| [head-acoustics-labcore](equipment/head-acoustics/head-acoustics-labcore.json) | 기종 | audio_analyzer | audio_performance | – | – | channels=≤32; data_rate_Hz=48000, 192000 | limited |
| [head-acoustics-sqobold](equipment/head-acoustics/head-acoustics-sqobold.json) | 기종 | acoustic_measurement |  | – | – | channels=4; weight_kg=≤0.485 | limited |
| [head-acoustics-squadriga-iii](equipment/head-acoustics/head-acoustics-squadriga-iii.json) | 기종 | acoustic_measurement |  | – | – | channels=8–16 | limited |

## Hegewald & Peschke (`hegewald-peschke`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [hegewald-peschke-at130-hardness](equipment/hegewald-peschke/hegewald-peschke-at130-hardness.json) | 계열 | rockwell_hardness | hardness_rockwell, hardness_brinell, hardness_vickers | – | – | load_N=29.4–1839; hardness_scales=HRA, HRB, HRC, HRD, HRF, HRG, HB/30, HRN 전 스케일 | catalog |
| [hegewald-peschke-bending-devices](equipment/hegewald-peschke/hegewald-peschke-bending-devices.json) | **부속** | grip_fixture | flexure | – | – |  | limited |
| [hegewald-peschke-bending-fatigue-wire](equipment/hegewald-peschke/hegewald-peschke-bending-fatigue-wire.json) | 계열 | mechanical_dynamic | fatigue, flexure | – | – | wire_diameter_mm=0.3–10; rotation_deg=≤180; stations=≤3; power_kW=≤4.0; weight_kg=300 | catalog |
| [hegewald-peschke-changing-devices](equipment/hegewald-peschke/hegewald-peschke-changing-devices.json) | **부속** | accessory | tensile | – | – | stage_travel_mm=≤300 | limited |
| [hegewald-peschke-compression-plates](equipment/hegewald-peschke/hegewald-peschke-compression-plates.json) | **부속** | grip_fixture | compression | 20–250 | – | specimen_diameter_mm=≤150 | limited |
| [hegewald-peschke-creep-loading-units](equipment/hegewald-peschke/hegewald-peschke-creep-loading-units.json) | 계열 | creep_tester | creep, relaxation | – | – | load_N=50–200; stations=5, 10 | limited |
| [hegewald-peschke-extensometers](equipment/hegewald-peschke/hegewald-peschke-extensometers.json) | **센서** | extensometer | tensile, compression, flexure | – | -70–1700 | gauge_length_mm=6–100; scan_range_mm=2–1100; displacement_um=≥0.1; data_rate_Hz=≤1600 | catalog |
| [hegewald-peschke-friction-test-stand](equipment/hegewald-peschke/hegewald-peschke-friction-test-stand.json) | 계열 | tribometer | friction_coefficient, friction_wear_tribo, abrasion | – | – | force_N=≤2000; sliding_speed_m_s=≤10; specimen_diameter_mm=≤50; wear_depth=≤2 | catalog |
| [hegewald-peschke-grips](equipment/hegewald-peschke/hegewald-peschke-grips.json) | **부속** | grip_fixture | tensile, compression, flexure, peel, tear, shear | 5–1200 | -40–1100 | specimen_thickness_mm=0–120; specimen_diameter_mm=4–60; pressure_bar=≤500 | catalog |
| [hegewald-peschke-high-temperature-furnaces](equipment/hegewald-peschke/hegewald-peschke-high-temperature-furnaces.json) | **부속** | furnace | tensile, compression, creep | – | 200–1250 | heating_rate_K_min=≤20; accuracy_degC=1–2; power_kW=≤2.5 | catalog |
| [hegewald-peschke-hot-hardness-1500c](equipment/hegewald-peschke/hegewald-peschke-hot-hardness-1500c.json) | 계열 | vickers_knoop_hardness | hardness_vickers | – | 300–1500 | load_N=≤300; hardness_scales=HV0.1, HV0.5, HV1, HV5, HV10, HV30; stage_travel_mm=≤25; specimen_size_mm=–; power_kW=≤4.5; weight_kg=≤350 | catalog |
| [hegewald-peschke-inspekt](equipment/hegewald-peschke/hegewald-peschke-inspekt.json) | 계열 | universal_testing_machine | tensile, compression, flexure, peel, shear | 100–2500 | – | crosshead_speed_mm_min=6e-05–1000; vertical_test_space_mm=1200–1900; horizontal_test_space_mm=610–1020; frame_stiffness_kN_mm=170–1685; weight_kg=1050–10000 | catalog |
| [hegewald-peschke-inspekt-blue](equipment/hegewald-peschke/hegewald-peschke-inspekt-blue.json) | 계열 | universal_testing_machine | tensile, compression, flexure, peel, shear | 5–50 | – | crosshead_speed_mm_min=0.00016–2000; vertical_test_space_mm=1070–1080; horizontal_test_space_mm=420; frame_stiffness_kN_mm=15–52; weight_kg=120–170 | catalog |
| [hegewald-peschke-inspekt-duo](equipment/hegewald-peschke/hegewald-peschke-inspekt-duo.json) | 계열 | universal_testing_machine | tensile, compression, flexure, peel, tear | 5–10 | – | crosshead_speed_mm_min=0.0008–1200; vertical_test_space_mm=1025–1325; frame_stiffness_kN_mm=10; weight_kg=83–88 | catalog |
| [hegewald-peschke-inspekt-micro](equipment/hegewald-peschke/hegewald-peschke-inspekt-micro.json) | 계열 | universal_testing_machine | tensile, compression, flexure | – | – | force_N=≤500; crosshead_speed_mm_min=0.0005–600; crosshead_travel_mm=≤50; position_resolution_nm=≤2; weight_kg=≤8.6 | catalog |
| [hegewald-peschke-inspekt-solo](equipment/hegewald-peschke/hegewald-peschke-inspekt-solo.json) | 계열 | universal_testing_machine | tensile, compression, flexure, peel, tear | ≤2.5 | – | crosshead_speed_mm_min=0.0015–1200; vertical_test_space_mm=475–1375; frame_stiffness_kN_mm=2.5–2.7; weight_kg=48–60 | catalog |
| [hegewald-peschke-inspekt-table](equipment/hegewald-peschke/hegewald-peschke-inspekt-table.json) | 계열 | universal_testing_machine | tensile, compression, flexure, peel, shear | 10–250 | – | crosshead_speed_mm_min=0.0005–2000; vertical_test_space_mm=1080–1170; horizontal_test_space_mm=420, 510; frame_stiffness_kN_mm=18–200; weight_kg=100–570 | catalog |
| [hegewald-peschke-inspekt-vario](equipment/hegewald-peschke/hegewald-peschke-inspekt-vario.json) | 계열 | universal_testing_machine | tensile, compression, flexure, shear | 100–2500 | – | vertical_test_space_mm=1900–5000; horizontal_test_space_mm=610, 750, 1000; crosshead_speed_mm_min=0.002–450; frame_stiffness_kN_mm=200; weight_kg=7200 | catalog |
| [hegewald-peschke-multi-impact-tester](equipment/hegewald-peschke/hegewald-peschke-multi-impact-tester.json) | 계열 | impact | drop_weight_impact, abrasion | – | – | impact_velocity_m_s=≤38.9; specimen_size_mm=–; measurement_distance_mm=150–600 | limited |
| [hegewald-peschke-peel-test-devices](equipment/hegewald-peschke/hegewald-peschke-peel-test-devices.json) | **부속** | grip_fixture | peel, friction_coefficient | – | – | specimen_orientation_deg=45–180 | limited |
| [hegewald-peschke-pendulum-impact](equipment/hegewald-peschke/hegewald-peschke-pendulum-impact.json) | 계열 | pendulum_impact | charpy_impact, izod_impact, tensile_impact | – | – | impact_energy_J=0.75–750; impact_velocity_m_s=0.39–5.5; data_rate_Hz=≤10000000 | catalog |
| [hegewald-peschke-pneumatic-grips](equipment/hegewald-peschke/hegewald-peschke-pneumatic-grips.json) | **부속** | grip_fixture | tensile | ≤20 | -70–280 |  | limited |
| [hegewald-peschke-rim-hardness-line](equipment/hegewald-peschke/hegewald-peschke-rim-hardness-line.json) | 계열 | brinell_hardness | hardness_brinell | 3.5 | – | test_time_s=30–60 | limited |
| [hegewald-peschke-rotational-impact-tester](equipment/hegewald-peschke/hegewald-peschke-rotational-impact-tester.json) | 계열 | high_speed_tensile | high_speed_tensile, tensile_impact | 0.1–80 | – | impact_velocity_m_s=1–14; impact_energy_J=≤16300; displacement_mm=≤3.6; data_rate_Hz=≤400000 | catalog |
| [hegewald-peschke-safety-doors](equipment/hegewald-peschke/hegewald-peschke-safety-doors.json) | **부속** | accessory |  | – | – |  | limited |
| [hegewald-peschke-shear-frame-testing-system](equipment/hegewald-peschke/hegewald-peschke-shear-frame-testing-system.json) | **부속** | grip_fixture | shear | – | – | force_N=0–200 | limited |
| [hegewald-peschke-specimen-cutting-presses](equipment/hegewald-peschke/hegewald-peschke-specimen-cutting-presses.json) | **부속** | specimen_preparation | tensile, tear | ≤30 | – |  | limited |
| [hegewald-peschke-t-groove-plates](equipment/hegewald-peschke/hegewald-peschke-t-groove-plates.json) | **부속** | grip_fixture | tensile, compression | – | – |  | limited |
| [hegewald-peschke-temperature-chambers](equipment/hegewald-peschke/hegewald-peschke-temperature-chambers.json) | **부속** | environmental_chamber | tensile, compression, flexure | – | -80–260 | heating_rate_K_min=≤10; cooling_rate_K_min=≤8; accuracy_degC=0.5–2; power_VA=2500–11500; weight_kg=80–300 | catalog |
| [hegewald-peschke-torsion](equipment/hegewald-peschke/hegewald-peschke-torsion.json) | 계열 | torsion_tester | torsion, fatigue | – | – | torque_Nm=200–5000; rotation_rpm=0.005–60; rotation_deg=–; specimen_diameter_mm=0.5–350; weight_kg=105–750 | catalog |
| [hegewald-peschke-torsion-modules](equipment/hegewald-peschke/hegewald-peschke-torsion-modules.json) | **부속** | accessory | torsion, tensile, compression | – | – |  | limited |

## Helmut Fischer (`helmut-fischer`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [helmut-fischer-dmp10-40-series](equipment/helmut-fischer/helmut-fischer-dmp10-40-series.json) | 계열 | coating_surface_test | coating_thickness | – | – |  | limited |
| [helmut-fischer-dualscope-fmp100-h-fmp150](equipment/helmut-fischer/helmut-fischer-dualscope-fmp100-h-fmp150.json) | 계열 | coating_surface_test | coating_thickness | – | – |  | limited |
| [helmut-fischer-fischerscope-mms-pc2](equipment/helmut-fischer/helmut-fischer-fischerscope-mms-pc2.json) | 기종 | coating_surface_test | coating_thickness | – | – |  | limited |
| [helmut-fischer-fischerscope-xray](equipment/helmut-fischer/helmut-fischer-fischerscope-xray.json) | 계열 | xrf_thickness | coating_thickness | – | – | coating_thickness_um=–; element_count=≤24; measurement_spot_um=≥20 | catalog |
| [helmut-fischer-mp0-series](equipment/helmut-fischer/helmut-fischer-mp0-series.json) | 계열 | coating_surface_test | coating_thickness | – | – | coating_thickness_um=0–2500 | limited |
| [helmut-fischer-phascope-pmp10](equipment/helmut-fischer/helmut-fischer-phascope-pmp10.json) | 기종 | coating_surface_test | coating_thickness | – | – | coating_thickness_um=1–200 | limited |

## HIKMICRO (`hikmicro`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [hikmicro-b-series](equipment/hikmicro/hikmicro-b-series.json) | 계열 | thermal_imager | thermography | – | -20–550 | ir_resolution_pixels=≤49152; thermal_sensitivity_degC=≤0.04; frame_rate_fps=25 | limited |
| [hikmicro-pocket-series](equipment/hikmicro/hikmicro-pocket-series.json) | 계열 | thermal_imager | thermography | – | -20–400 | ir_resolution_pixels=9216–49152; thermal_sensitivity_degC=0.04–0.05 | limited |
| [hikmicro-sp-series](equipment/hikmicro/hikmicro-sp-series.json) | 계열 | thermal_imager | thermography | – | -40–2200 | ir_resolution_pixels=172800–1310720; thermal_sensitivity_degC=0.02–0.03; frame_rate_fps=30 | limited |

## HIOKI (`hioki`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [hioki-dt4280-dmm](equipment/hioki/hioki-dt4280-dmm.json) | 계열 | dmm_daq |  | – | – | dmm_display_counts=60000; voltage_V=0.06–1000; resistance_ohm=60–600000000 | limited |
| [hioki-im3570-impedance-analyzer](equipment/hioki/hioki-im3570-impedance-analyzer.json) | 계열 | network_lcr_analyzer |  | – | – | frequency_Hz=4–5000000; impedance_ohm=0.1–100000000; measurement_time_s=≤0.0005 | limited |
| [hioki-im3590-chemical-impedance-analyzer](equipment/hioki/hioki-im3590-chemical-impedance-analyzer.json) | 계열 | network_lcr_analyzer |  | – | – | frequency_Hz=0.001–200000 | limited |
| [hioki-im35xx-lcr-meters](equipment/hioki/hioki-im35xx-lcr-meters.json) | 계열 | network_lcr_analyzer |  | – | – | frequency_Hz=0.001–8000000; impedance_ohm=0.1–100000000; measurement_time_s=≤0.002 | limited |
| [hioki-im7580-impedance-analyzers](equipment/hioki/hioki-im7580-impedance-analyzers.json) | 계열 | network_lcr_analyzer |  | – | – | frequency_Hz=100000–3000000000; measurement_time_s=≤0.0005 | limited |
| [hioki-lr8400](equipment/hioki/hioki-lr8400.json) | 계열 | dmm_daq |  | – | – | channels=30–60; data_interval_ms=10–50; voltage_V=0.01–100 | limited |
| [hioki-lr8450](equipment/hioki/hioki-lr8450.json) | 계열 | dmm_daq |  | – | – | channels=≤330; data_interval_ms=≤1 | limited |
| [hioki-mr6000](equipment/hioki/hioki-mr6000.json) | 계열 | dmm_daq |  | – | – | channels=≤32; data_rate_Hz=≤200000000; bandwidth_Hz=0–30000000; voltage_V=0.01–400 | limited |
| [hioki-mr8875](equipment/hioki/hioki-mr8875.json) | 계열 | dmm_daq |  | – | – |  | limited |
| [hioki-st5520-insulation-tester](equipment/hioki/hioki-st5520-insulation-tester.json) | 기종 | insulation_tester | insulation_resistance | – | – | insulation_test_voltage_V=25–1000; insulation_resistance_ohm=0–4000000000; response_time_ms=≤20 | catalog |

## Hirayama Manufacturing (`hirayama`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [hirayama-hast-pc-r9](equipment/hirayama/hirayama-hast-pc-r9.json) | 계열 | hast_chamber | hast, damp_heat | – | 105–162.5 | humidity_pct=65–100; chamber_volume_L=26–84.4; pressure_MPa=0.019–0.393 | limited |

## Hirox Co., Ltd. (`hirox`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [hirox-digital-microscopes](equipment/hirox/hirox-digital-microscopes.json) | 계열 | optical_microscope | microscopy | – | – | magnification=≤10000; stage_travel_mm=≤100 | limited |

## Hitachi High-Tech Analytical Science (`hitachi-high-tech`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [hitachi-nexta-dma200](equipment/hitachi-high-tech/hitachi-nexta-dma200.json) | 계열 | dma | dma | – | -150–600 | frequency_Hz=0.01–200; force_N=≤20 | limited |
| [hitachi-nexta-dsc](equipment/hitachi-high-tech/hitachi-nexta-dsc.json) | 계열 | dsc | dsc | – | -150–725 | heating_rate_K_min=0.01–100 | limited |
| [hitachi-nexta-sta](equipment/hitachi-high-tech/hitachi-nexta-sta.json) | 계열 | sta | tga, dsc | – | 20–1500 | balance_resolution_ug=– | catalog |
| [hitachi-su3800-3900-sem](equipment/hitachi-high-tech/hitachi-su3800-3900-sem.json) | 계열 | electron_microscope | microscopy, composition_analysis | – | – |  | limited |
| [hitachi-tma7000](equipment/hitachi-high-tech/hitachi-tma7000.json) | 계열 | tma | tma, creep, relaxation, dma | – | -170–1500 | force_N=≤5.8; heating_rate_K_min=0.01–100 | limited |

## Hitachi Power Solutions Co., Ltd. (`hitachi-power-solutions`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [hitachi-power-solutions-array-sat](equipment/hitachi-power-solutions/hitachi-power-solutions-array-sat.json) | 계열 | acoustic_microscope | acoustic_delamination | – | – | transducer_frequency_MHz=10–75; scan_range_mm=≤2000; wafer_size_mm=100–300 | limited |
| [hitachi-power-solutions-finesat](equipment/hitachi-power-solutions/hitachi-power-solutions-finesat.json) | 계열 | acoustic_microscope | acoustic_delamination | – | – | transducer_frequency_MHz=5–400; scan_range_mm=≤350; measuring_speed_mm_s=≤2000 | limited |

## HORIBA Scientific (`horiba`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [horiba-fluoromax-plus](equipment/horiba/horiba-fluoromax-plus.json) | 기종 | optical_spectrometer | optical_spectroscopy, xray_void_inspection | – | -40.0–150.0 |  | catalog |
| [horiba-gd-profiler-2](equipment/horiba/horiba-gd-profiler-2.json) | 기종 | composition_spectrometer | composition_analysis, surface_topography | – | – |  | catalog |

## Hot Disk AB (`hot-disk`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [hot-disk-tps-2200](equipment/hot-disk/hot-disk-tps-2200.json) | 기종 | thermal_conductivity | thermal_conductivity | – | -50.0–750.0 |  | catalog |
| [hot-disk-tps-2500-s](equipment/hot-disk/hot-disk-tps-2500-s.json) | 기종 | thermal_conductivity | thermal_conductivity | – | -253–1000 | thermal_conductivity_W_mK=0.005–1800; thermal_diffusivity_mm2_s=0.01–1400; specimen_thickness_mm=≥0.01; measurement_time_s=1–2560 | catalog |
| [hot-disk-tps-2500-s-materialtwin](equipment/hot-disk/hot-disk-tps-2500-s-materialtwin.json) | 계열 (보탬→hot-disk-tps-2500-s) | thermal_conductivity | thermal_conductivity | – | – |  | catalog |

## IMADA Co., Ltd. (`imada`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [imada-motorized-test-stands](equipment/imada/imada-motorized-test-stands.json) | 계열 | force_tester | tensile, compression, peel | – | – | force_N=≤5000; crosshead_speed_mm_min=0.5–600 | catalog |
| [imada-zt-series-force-gauges](equipment/imada/imada-zt-series-force-gauges.json) | 계열 | force_pressure_sensor | tensile, compression | – | – | force_N=2–5000; digital_sample_rate_Hz=≤2000; operating_temperature_degC=0–40; operating_humidity_pct=20–80 | catalog |

## Imetrum Ltd (`imetrum`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [imetrum-uvx3d-video-gauge](equipment/imetrum/imetrum-uvx3d-video-gauge.json) | 계열 | dic_strain_measurement | tensile, compression | – | -100–370 | gauge_length_mm=10–200; position_resolution_nm=≤500.0; data_rate_Hz=120, 500, 1000; following_speed_mm_min=≤2500; working_distance_mm=320–360 | limited |

## IMV Corporation (`imv`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [imv-a-series-shaker](equipment/imv/imv-a-series-shaker.json) | 계열 | vibration_shaker | vibration_sine_random, mechanical_shock | 11–74 | – | payload_kg=200–1000; stroke_mm_pk_pk=76.2 | limited |
| [imv-i-series-shaker](equipment/imv/imv-i-series-shaker.json) | 계열 | vibration_shaker | vibration_sine_random, mechanical_shock | 8–65 | – | frequency_Hz=0–3300; displacement_mm=≤100; velocity_m_s=≤4.6; payload_kg=– | catalog |
| [imv-k-series-shaker](equipment/imv/imv-k-series-shaker.json) | 계열 | vibration_shaker | vibration_sine_random, mechanical_shock | 30.8–350 | – | force_shock_kN=≤750; payload_kg=500–3000 | limited |
| [imv-m-series-shaker](equipment/imv/imv-m-series-shaker.json) | 계열 | vibration_shaker | vibration_sine_random | – | – | force_N=300–1300; payload_kg=10–120; frequency_Hz=≤2000 | limited |
| [imv-pet-series-shaker](equipment/imv/imv-pet-series-shaker.json) | 계열 | vibration_shaker | vibration_sine_random | – | – | force_N=9.8–49; payload_kg=≤3; frequency_Hz=≤40000 | limited |

## INFICON (`inficon`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [inficon-leak-detectors](equipment/inficon/inficon-leak-detectors.json) | 계열 | helium_leak_detector | leak_rate | – | – | leak_rate_mbar_L_s=≥5e-12; helium_pumping_speed_L_s=≤36 | catalog |

## InfraTec GmbH (`infratec`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [infratec-imageir](equipment/infratec/infratec-imageir.json) | 계열 | thermal_imager | thermography | – | – | ir_resolution_pixels=327680–2949120; frame_rate_fps=113–1105; max_frame_rate_fps=≤30330; thermal_sensitivity_degC=0.02–0.035 | limited |
| [infratec-variocam-hdx](equipment/infratec/infratec-variocam-hdx.json) | 계열 | thermal_imager | thermography | – | – | ir_resolution_pixels=≤786432 | limited |

## INNOVATEST (`innovatest`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [innovatest-nexus-3200](equipment/innovatest/innovatest-nexus-3200.json) | 기종 | brinell_hardness | hardness_brinell | – | – | test_load_kgf=62.5–3000; hardness_scales=HBW 2.5/62.5, HBW 2.5/187.5, HBW 5/62.5, HBW 5/125, HBW 5/250, HBW 5/750, HBW 10/100, HBW 10/125; specimen_height_mm=≤2 | catalog |

## Instron (`instron`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [instron-2527-dynacell-load-cells](equipment/instron/instron-2527-dynacell-load-cells.json) | **센서** | load_cell | fatigue, tensile, compression, torsion | – | – |  | limited |
| [instron-2580-2530-static-load-cells](equipment/instron/instron-2580-2530-static-load-cells.json) | **센서** | load_cell | tensile, compression | – | – | force_N=2.5–600000 | limited |
| [instron-2601-lvdt-compression-deflectometers](equipment/instron/instron-2601-lvdt-compression-deflectometers.json) | **센서** | extensometer | compression, flexure, tensile | – | -40–100 | displacement_mm=0.5–100 | limited |
| [instron-2603-long-travel-extensometer](equipment/instron/instron-2603-long-travel-extensometer.json) | **센서** | extensometer | tensile | – | – | displacement_mm=250–750; gauge_length_mm=10–200 | limited |
| [instron-2630-static-axial-clip-on-extensometers](equipment/instron/instron-2630-static-axial-clip-on-extensometers.json) | **센서** | extensometer | tensile, flexure, compression | – | -100–200 | gauge_length_mm=8–100 | limited |
| [instron-2650-biaxial-averaging-clip-on-extensometers](equipment/instron/instron-2650-biaxial-averaging-clip-on-extensometers.json) | **센서** | extensometer | tensile, compression | – | -200–200 | gauge_length_mm=25–50.8 | limited |
| [instron-2670-crack-opening-displacement-gauges](equipment/instron/instron-2670-crack-opening-displacement-gauges.json) | **센서** | extensometer | fracture_toughness, fatigue | – | -200–200 | gauge_length_mm=5–10; displacement_mm=≤4 | limited |
| [instron-2701-air-kits-for-pneumatic-grips](equipment/instron/instron-2701-air-kits-for-pneumatic-grips.json) | **부속** | accessory | tensile | – | – | pressure_bar=≤8.3 | limited |
| [instron-2710-screw-side-action-grips](equipment/instron/instron-2710-screw-side-action-grips.json) | **부속** | grip_fixture | tensile, shear | – | – | force_N=100–10000; specimen_thickness_mm=≤46 | limited |
| [instron-2711-fiber-filament-tensile-grips](equipment/instron/instron-2711-fiber-filament-tensile-grips.json) | **부속** | grip_fixture | tensile | – | -10–100 | force_N=0.825–5 | limited |
| [instron-2712-pneumatic-side-action-grips](equipment/instron/instron-2712-pneumatic-side-action-grips.json) | **부속** | grip_fixture | tensile | – | – | force_N=50–10000 | limited |
| [instron-2713-self-tightening-eccentric-roller-grips](equipment/instron/instron-2713-self-tightening-eccentric-roller-grips.json) | **부속** | grip_fixture | tensile | – | -70–315 | force_N=100–5000; width_mm=≤43 | limited |
| [instron-2714-pneumatic-cord-and-yarn-grips](equipment/instron/instron-2714-pneumatic-cord-and-yarn-grips.json) | **부속** | grip_fixture | tensile | – | – | force_N=50–2000; specimen_diameter_mm=≤4.8 | limited |
| [instron-2715-capstan-tensile-grips](equipment/instron/instron-2715-capstan-tensile-grips.json) | **부속** | grip_fixture | tensile | 2.5–50 | -73–316 |  | limited |
| [instron-2716-110-pneumatic-wedge-action-grips](equipment/instron/instron-2716-110-pneumatic-wedge-action-grips.json) | **부속** | grip_fixture | tensile | 100–200 | – | specimen_diameter_mm=≤60; specimen_thickness_mm=≤70 | limited |
| [instron-2716-mechanical-wedge-action-grips](equipment/instron/instron-2716-mechanical-wedge-action-grips.json) | **부속** | grip_fixture | tensile | 1–250 | -70–350 | width_mm=≤50 | limited |
| [instron-2717-080-fabric-loop-grips](equipment/instron/instron-2717-080-fabric-loop-grips.json) | **부속** | grip_fixture | tensile | – | – |  | limited |
| [instron-2717-o-ring-test-fixtures](equipment/instron/instron-2717-o-ring-test-fixtures.json) | **부속** | grip_fixture | tensile | ≤1 | – |  | limited |
| [instron-2717-threaded-and-button-end-grips](equipment/instron/instron-2717-threaded-and-button-end-grips.json) | **부속** | grip_fixture | tensile | 100–267 | -70–350 | specimen_diameter_mm=≤38 | limited |
| [instron-2718-hydraulic-grip-pumps](equipment/instron/instron-2718-hydraulic-grip-pumps.json) | **부속** | accessory | tensile | ≤600 | – | pressure_bar=41–207 | limited |
| [instron-2742-fatigue-rated-wedge-grips](equipment/instron/instron-2742-fatigue-rated-wedge-grips.json) | **부속** | grip_fixture | fatigue, tensile, torsion | – | – | dynamic_force_kN=1–100; torque_Nm=≤100 | limited |
| [instron-2750-compact-tension-fixtures](equipment/instron/instron-2750-compact-tension-fixtures.json) | **부속** | grip_fixture | fracture_toughness, fatigue | – | ≤1000 | static_force_kN=0.8–500; dynamic_force_kN=10–250; specimen_thickness_mm=12.5–50 | limited |
| [instron-2810-005-coefficient-of-friction-fixture](equipment/instron/instron-2810-005-coefficient-of-friction-fixture.json) | **부속** | grip_fixture | friction_coefficient | – | – |  | limited |
| [instron-2810-fatigue-flexure-fixtures](equipment/instron/instron-2810-fatigue-flexure-fixtures.json) | **부속** | grip_fixture | flexure, fatigue | 3–500 | – |  | limited |
| [instron-2810-flexure-fixtures](equipment/instron/instron-2810-flexure-fixtures.json) | **부속** | grip_fixture | flexure | 5–250 | -100–350 | hdt_span_mm=10–600; width_mm=≤100 | limited |
| [instron-2820-033-miniature-variable-angle-peel-fixture](equipment/instron/instron-2820-033-miniature-variable-angle-peel-fixture.json) | **부속** | grip_fixture | peel | ≤1 | 10–60 | specimen_orientation_deg=30–150 | limited |
| [instron-2850-t-slot-tables](equipment/instron/instron-2850-t-slot-tables.json) | **부속** | grip_fixture | tensile, compression, flexure, peel | 5–600 | – |  | limited |
| [instron-2860-translation-and-clamping-stages](equipment/instron/instron-2860-translation-and-clamping-stages.json) | **부속** | grip_fixture | tensile, wire_bond_strength | ≤1 | – | stage_travel_mm=≤12.5 | limited |
| [instron-2910-component-test-plates](equipment/instron/instron-2910-component-test-plates.json) | **부속** | grip_fixture | tensile, compression, flexure, peel, puncture | 1–30 | – |  | limited |
| [instron-2910-load-frame-support-tables](equipment/instron/instron-2910-load-frame-support-tables.json) | **부속** | accessory |  | – | – |  | limited |
| [instron-3119-160-furnace](equipment/instron/instron-3119-160-furnace.json) | **부속** | furnace | tensile, creep, fatigue | – | 200–1050 | heated_length_mm=300; bore_diameter_mm=75 | catalog |
| [instron-3119-600-environmental-chambers](equipment/instron/instron-3119-600-environmental-chambers.json) | **부속** | environmental_chamber | tensile, compression, flexure, fatigue | – | -150–600 |  | catalog |
| [instron-3400-series](equipment/instron/instron-3400-series.json) | 계열 | universal_testing_machine | tensile, compression, flexure, peel, puncture, friction_coefficient, shear, tear | 0.5–300 | – | crosshead_speed_mm_min=5e-05–1016; vertical_test_space_mm=651–1744; horizontal_test_space_mm=100–575; data_rate_Hz=≤1000 | catalog |
| [instron-5900-series](equipment/instron/instron-5900-series.json) | 계열 | universal_testing_machine | tensile, compression, flexure, shear, peel, tear, fatigue, creep | 0.5–600 | – | crosshead_speed_mm_min=0.0001–3000; vertical_test_space_mm=726–2050; horizontal_test_space_mm=100–763; data_rate_Hz=≤2500 | catalog |
| [instron-5900-series-materialtwin](equipment/instron/instron-5900-series-materialtwin.json) | 계열 (보탬→instron-5900-series) | universal_testing_machine | tensile, compression, flexure, shear, peel, tear, fatigue, creep | – | – |  | limited |
| [instron-6800-series](equipment/instron/instron-6800-series.json) | 계열 | universal_testing_machine | tensile, compression, flexure, peel, puncture, friction_coefficient, shear, tear, creep, relaxation | 0.5–300 | -150–1200 (부속) | crosshead_speed_mm_min=5e-05–3048; vertical_test_space_mm=738–1993; horizontal_test_space_mm=100–947; data_rate_Hz=≤5000 | catalog |
| [instron-8800-servohydraulic](equipment/instron/instron-8800-servohydraulic.json) | 계열 | servohydraulic_fatigue | fatigue, fracture_toughness, tensile, compression, flexure, torsion, high_speed_tensile | – | – | dynamic_force_kN=25–250; torque_Nm=100; stroke_mm=100; frequency_Hz=–; vertical_test_space_mm=≤1067 | catalog |
| [instron-8800-servohydraulic-web](equipment/instron/instron-8800-servohydraulic-web.json) | 계열 (보탬→instron-8800-servohydraulic) | servohydraulic_fatigue | fatigue | – | – |  | catalog |
| [instron-9400-drop-tower](equipment/instron/instron-9400-drop-tower.json) | 계열 | drop_tower_impact | drop_weight_impact, puncture, tensile_impact | 0.45–222 | – | impact_energy_J=0.15–1800; impact_velocity_m_s=0.77–24; drop_height_m=0.03–29.4; drop_mass_kg=0.5–70 | catalog |
| [instron-9400-drop-tower-materialtwin](equipment/instron/instron-9400-drop-tower-materialtwin.json) | 계열 (보탬→instron-9400-drop-tower) | drop_tower_impact | drop_weight_impact, puncture, tensile_impact | – | – |  | limited |
| [instron-advanced-hydraulic-wedge-action-grips](equipment/instron/instron-advanced-hydraulic-wedge-action-grips.json) | **부속** | grip_fixture | tensile, fatigue, compression | – | 4–65 | static_force_kN=30–600; dynamic_force_kN=30–500 | limited |
| [instron-autox750-automatic-contacting-extensometer](equipment/instron/instron-autox750-automatic-contacting-extensometer.json) | **센서** | extensometer | tensile, flexure | – | – | displacement_mm=≤750 | limited |
| [instron-ave-video-extensometer](equipment/instron/instron-ave-video-extensometer.json) | **센서** | extensometer | tensile, compression, flexure | – | – | field_of_view_mm=85–840; gauge_length_mm=≥2.5; data_rate_Hz=≤500; following_speed_mm_min=≤2500 | catalog |
| [instron-ceast-9050-pendulum](equipment/instron/instron-ceast-9050-pendulum.json) | 계열 | pendulum_impact | charpy_impact, izod_impact, tensile_impact | – | – | impact_energy_J=0.5–50; impact_velocity_m_s=1–3.8; specimen_diameter_mm=≤25 | catalog |
| [instron-ceast-melt-flow-mf](equipment/instron/instron-ceast-melt-flow-mf.json) | 계열 | melt_flow_indexer | melt_flow | – | – | melt_temperature_degC=30–400; melt_load_kg=0.325–21.6 | catalog |
| [instron-debris-shields](equipment/instron/instron-debris-shields.json) | **부속** | accessory | tensile, compression | – | – |  | limited |
| [instron-electropuls-e1000-e10000-e20000](equipment/instron/instron-electropuls-e1000-e10000-e20000.json) | 계열 | electrodynamic_fatigue | fatigue, torsion | – | – | dynamic_force_kN=1, 10, 20; static_force_kN=7, 14; stroke_mm=60, 75; torque_Nm=100, 130; rotation_deg=≤135; frequency_Hz=≤100; vertical_test_space_mm=877, 956 | catalog |
| [instron-electropuls-e3000](equipment/instron/instron-electropuls-e3000.json) | 기종 | electrodynamic_fatigue | fatigue, tensile, compression, flexure, torsion, dma | – | – | dynamic_force_kN=≤3; static_force_kN=≤2.1; torque_Nm=≤25; stroke_mm=60; rotation_deg=≤135; frequency_Hz=≤100; vertical_test_space_mm=≤861; horizontal_test_space | catalog |
| [instron-electropuls-safety-guards](equipment/instron/instron-electropuls-safety-guards.json) | **부속** | accessory | fatigue | – | – |  | limited |
| [instron-fastener-shear-fixtures](equipment/instron/instron-fastener-shear-fixtures.json) | **부속** | grip_fixture | shear | – | – | pressure_MPa=≤1380 | limited |
| [instron-high-temperature-extensometers](equipment/instron/instron-high-temperature-extensometers.json) | **센서** | extensometer | tensile, compression, fatigue, creep, relaxation | – | ≤1200 | gauge_length_mm=12.5–50 | limited |
| [instron-hv-series-hdt-vicat](equipment/instron/instron-hv-series-hdt-vicat.json) | 계열 | hdt_vicat | hdt, vicat | – | 20–500 | stations=3, 6; heating_rate_K_h=50, 120 | catalog |
| [instron-hydraulic-side-action-grips-durasync](equipment/instron/instron-hydraulic-side-action-grips-durasync.json) | **부속** | grip_fixture | tensile, fatigue | 250–600 | – | specimen_diameter_mm=3–60; specimen_thickness_mm=≤100; pressure_bar=≤131 | limited |
| [instron-industrial-series-static-hydraulic](equipment/instron/instron-industrial-series-static-hydraulic.json) | 계열 | hydraulic_utm | tensile, compression, flexure, shear | 600, 1000, 1500, 2000 | – | crosshead_speed_mm_min=0.1–203; crosshead_travel_mm=152, 254, 610 | catalog |
| [instron-microelectronics-tensile-grips](equipment/instron/instron-microelectronics-tensile-grips.json) | **부속** | grip_fixture | tensile, wire_bond_strength | – | – | force_N=10–500; specimen_thickness_mm=≤0.8 | limited |
| [instron-mt-microtorsion](equipment/instron/instron-mt-microtorsion.json) | 계열 | torsion_tester | torsion | – | – | torque_Nm=0.225–225; rotation_rpm=0.01–120; rotation_deg=≤5400000; specimen_diameter_mm=≤203; test_opening_mm=381–775 | catalog |
| [instron-puncture-fixtures](equipment/instron/instron-puncture-fixtures.json) | **부속** | grip_fixture | puncture | 2.5–4.4 | – |  | limited |
| [instron-spherically-seated-compression-platens](equipment/instron/instron-spherically-seated-compression-platens.json) | **부속** | grip_fixture | compression | 10–5000 | – | specimen_diameter_mm=≤305 | limited |
| [instron-t-grip-lever-action-wedge-grips](equipment/instron/instron-t-grip-lever-action-wedge-grips.json) | **부속** | grip_fixture | tensile | 22.2–150 | – |  | limited |
| [instron-transverse-clip-on-extensometers](equipment/instron/instron-transverse-clip-on-extensometers.json) | **센서** | extensometer | tensile | – | -40–100 | width_mm=0–25 | limited |
| [instron-w-5155-fastener-holders](equipment/instron/instron-w-5155-fastener-holders.json) | **부속** | grip_fixture | tensile | 100–1500 | – | specimen_diameter_mm=≤72 | limited |
| [instron-w-5300-hydraulic-wedge-action-grips](equipment/instron/instron-w-5300-hydraulic-wedge-action-grips.json) | **부속** | grip_fixture | tensile | 300–2000 | – | specimen_diameter_mm=≤90; specimen_thickness_mm=≤90 | limited |
| [instron-w-5510-torsion-load-cells](equipment/instron/instron-w-5510-torsion-load-cells.json) | **센서** | load_cell | torsion | – | – | torque_Nm=0.225–220 | limited |
| [instron-wire-and-cable-tensile-grips](equipment/instron/instron-wire-and-cable-tensile-grips.json) | **부속** | grip_fixture | tensile | 2.2–90 | -10–80 | wire_diameter_mm=0.125–12.7 | limited |

## Instrument Systems (`instrument-systems`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [instrument-systems-lumicam-4000b](equipment/instrument-systems/instrument-systems-lumicam-4000b.json) | 계열 | imaging_colorimeter | photometry_colorimetry | – | – | luminance_cd_m2=0.0003–4300000; resolution_pixels=≤12288000; dynamic_range=≤43000000000 | catalog |

## Interface, Inc. (`interface`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [interface-lowprofile-load-cells](equipment/interface/interface-lowprofile-load-cells.json) | **센서** | force_pressure_sensor |  | 0.111–5000 | – |  | limited |
| [interface-tension-compression-load-cells](equipment/interface/interface-tension-compression-load-cells.json) | **센서** | force_pressure_sensor |  | 0.02–50 | – |  | limited |

## iTS GmbH (`its-gmbh`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [its-gmbh-immersion-tanks](equipment/its-gmbh/its-gmbh-immersion-tanks.json) | 계열 | water_ingress_tester | water_ingress | – | – | ipx_levels=–; immersion_depth_m=≤1.3; payload_kg=≤80 | limited |
| [its-gmbh-ipx-room-solutions](equipment/its-gmbh/its-gmbh-ipx-room-solutions.json) | 계열 | water_ingress_tester | water_ingress | – | – | ipx_levels=–; oscillating_tube_radius_mm=≤1200; spray_flow_L_min=0–105; water_pressure_bar=0–120; water_temperature_degC=≤85; turntable_speed_rpm=0–5; turntable | limited |
| [its-gmbh-spk-water-test-chambers](equipment/its-gmbh/its-gmbh-spk-water-test-chambers.json) | 계열 | water_ingress_tester | water_ingress | – | – | ipx_levels=–; oscillating_tube_radius_mm=200, 400, 600, 800; turntable_speed_rpm=1–5; spray_flow_L_min=0–106; water_pressure_bar=0–160; water_temperature_degC=1 | limited |

## J.A. Woollam (`ja-woollam`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [woollam-rc2](equipment/ja-woollam/woollam-rc2.json) | 기종 | film_thickness_analyzer | coating_thickness | – | ≤300.0 |  | catalog |

## Jandel Engineering Ltd (`jandel`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [jandel-four-point-probe-test-units](equipment/jandel/jandel-four-point-probe-test-units.json) | 계열 | electrical_property_tester | electrical_transport | – | – | surface_resistivity_ohm_sq=0.001–100000000.0; resistivity_ohm_cm=0.001–1000000.0; current_A=1e-08–0.1; voltage_V=1e-06–4 | limited |

## JEIO TECH (`jeio-tech`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [jeio-tech-th3-chambers](equipment/jeio-tech/jeio-tech-th3-chambers.json) | 계열 | climatic_chamber | damp_heat | – | -70–100 | humidity_pct=≤95 | limited |

## JEOL (`jeol`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [jeol-jamp-9510f](equipment/jeol/jeol-jamp-9510f.json) | 기종 | composition_spectrometer | composition_analysis | – | – |  | catalog |
| [jeol-jem-f200](equipment/jeol/jeol-jem-f200.json) | 기종 | electron_microscope | microscopy, crystal_structure_analysis | – | – |  | limited |
| [jeol-jps-9030](equipment/jeol/jeol-jps-9030.json) | 기종 | composition_spectrometer | composition_analysis | – | – |  | limited |
| [jeol-jsm-it-fesem](equipment/jeol/jeol-jsm-it-fesem.json) | 계열 | electron_microscope | composition_analysis, crystal_structure_analysis | – | – |  | catalog |
| [jeol-jsx-1000s](equipment/jeol/jeol-jsx-1000s.json) | 기종 | composition_spectrometer | composition_analysis | – | – |  | catalog |
| [jeol-jxa-epma](equipment/jeol/jeol-jxa-epma.json) | 계열 | electron_microscope | composition_analysis | – | – |  | catalog |
| [jeol-xtalab-synergy-ed](equipment/jeol/jeol-xtalab-synergy-ed.json) | 기종 | xray_diffractometer | crystal_structure_analysis | – | – |  | catalog |

## Keithley (Tektronix) (`keithley`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [keithley-2010-dmm](equipment/keithley/keithley-2010-dmm.json) | 계열 | dmm_daq |  | – | – |  | limited |
| [keithley-2100-usb-dmm](equipment/keithley/keithley-2100-usb-dmm.json) | 계열 | dmm_daq |  | – | – |  | limited |
| [keithley-2700-integra](equipment/keithley/keithley-2700-integra.json) | 계열 | dmm_daq |  | – | – |  | catalog |
| [keithley-3700a](equipment/keithley/keithley-3700a.json) | 계열 | dmm_daq |  | – | – | channels=≤576 | limited |
| [keithley-4200-scs](equipment/keithley/keithley-4200-scs.json) | 계열 | electrical_property_tester | electrical_transport | – | – |  | catalog |
| [keithley-daq6510](equipment/keithley/keithley-daq6510.json) | 계열 | dmm_daq |  | – | – |  | limited |
| [keithley-dmm6500](equipment/keithley/keithley-dmm6500.json) | 계열 | dmm_daq |  | – | – |  | limited |
| [keithley-dmm7510-dmm7512](equipment/keithley/keithley-dmm7510-dmm7512.json) | 계열 | dmm_daq |  | – | – | dmm_resolution_digits=7.5; data_rate_Hz=≤1000000 | limited |

## KEYENCE (`keyence`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [keyence-cl-3000](equipment/keyence/keyence-cl-3000.json) | 계열 | thickness_displacement_gauge |  | – | – | displacement_mm=-10–10; measurement_distance_mm=10–70; spot_size_um=3.5–300; linearity_um=0.22–2.2; position_resolution_nm=≥250 | limited |
| [keyence-gt2](equipment/keyence/keyence-gt2.json) | 계열 | thickness_displacement_gauge |  | – | – | displacement_mm=0–50; position_resolution_nm=100–500; stylus_force_mN=200–3200 | limited |
| [keyence-im-8000](equipment/keyence/keyence-im-8000.json) | 계열 | coordinate_measuring_machine |  | – | – | field_of_view_mm=≤300; measuring_repeatability_um=0.5–2; detector_megapixels=20; table_load_kg=5–7.5 | limited |
| [keyence-lj-x8000](equipment/keyence/keyence-lj-x8000.json) | 계열 | thickness_displacement_gauge | surface_topography | – | – | displacement_mm=-400–400; measuring_range_x_mm=7–720; measurement_distance_mm=20–980; measuring_repeatability_um=0.3–10; laser_wavelength_nm=405 | limited |
| [keyence-lk-g5000](equipment/keyence/keyence-lk-g5000.json) | 계열 | thickness_displacement_gauge |  | – | – | displacement_mm=-40–40; measurement_distance_mm=8–150; measuring_repeatability_um=≥0.005; linearity_pct_fs=≥0.02; data_rate_Hz=≤392000; spot_size_um=20–120 | limited |
| [keyence-lm-x](equipment/keyence/keyence-lm-x.json) | 계열 | coordinate_measuring_machine |  | – | – | field_of_view_mm=≤325; measuring_repeatability_um=≥0.1 | limited |
| [keyence-si-f](equipment/keyence/keyence-si-f.json) | 계열 | thickness_displacement_gauge |  | – | – | spot_size_um=20–40; linearity_um=0.3; sampling_cycle_us=200; laser_wavelength_nm=820 | limited |
| [keyence-vhx-7000-series](equipment/keyence/keyence-vhx-7000-series.json) | 계열 | optical_microscope | microscopy | – | – | magnification=20–6000; detector_megapixels=3.19–12.22; data_rate_Hz=≤50 | limited |
| [keyence-vhx-x1-series](equipment/keyence/keyence-vhx-x1-series.json) | 계열 | optical_microscope | microscopy | – | – | magnification=5–6000; detector_megapixels=3.19–12.22; data_rate_Hz=≤50; operating_temperature_degC=5–40 | limited |
| [keyence-vk-x3000-series](equipment/keyence/keyence-vk-x3000-series.json) | 계열 | optical_profilometer | surface_topography, microscopy | – | – | laser_wavelength_nm=404, 661; magnification=42–28800; field_of_view_mm=0.011–7.398; vertical_resolution_nm=0.1–1; stage_travel_mm=≤100; scan_range_mm=≤50 | limited |
| [keyence-vl-700](equipment/keyence/keyence-vl-700.json) | 계열 | coordinate_measuring_machine |  | – | – | measuring_repeatability_um=2; table_load_kg=≤50 | limited |
| [keyence-xm](equipment/keyence/keyence-xm.json) | 계열 | coordinate_measuring_machine |  | – | – | measuring_range_x_mm=≤2000; measuring_range_y_mm=≤1200; measuring_range_z_mm=≤1000 | limited |

## Keysight Technologies (`keysight`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [keysight-33500b-trueform](equipment/keysight/keysight-33500b-trueform.json) | 계열 | signal_generator |  | – | – | bandwidth_Hz=20000000, 30000000; channels=1, 2; sample_rate_Sa_s=160000000, 250000000; dac_resolution_bit=16; output_voltage_V=0.001–10; waveform_memory_pts=100 | limited |
| [keysight-33600a-trueform](equipment/keysight/keysight-33600a-trueform.json) | 계열 | signal_generator |  | – | – | bandwidth_Hz=80000000, 120000000; channels=1, 2; sample_rate_Sa_s=660000000, 1000000000; dac_resolution_bit=14; output_voltage_V=0.001–10; waveform_memory_pts=4 | limited |
| [keysight-3458a-dmm](equipment/keysight/keysight-3458a-dmm.json) | 계열 | dmm_daq |  | – | – |  | limited |
| [keysight-34980a](equipment/keysight/keysight-34980a.json) | 계열 | dmm_daq |  | – | – |  | limited |
| [keysight-8960-series-10](equipment/keysight/keysight-8960-series-10.json) | 계열 | radio_communication_tester |  | – | – | frequency_Hz=292000000–2700000000; rf_output_level_dBm=-110–-13; radio_standards=GSM/GPRS/EGPRS/E-EDGE, W-CDMA/HSPA/HSPA+, DC-HSDPA, cdma2000/1xEV-DO/eHRPD, TD- | limited |
| [keysight-daq970a](equipment/keysight/keysight-daq970a.json) | 계열 | dmm_daq |  | – | – | channels=≤120; channel_scan_rate_ch_s=≤450; dmm_resolution_digits=6.5 | limited |
| [keysight-e4980-precision-lcr](equipment/keysight/keysight-e4980-precision-lcr.json) | 계열 | network_lcr_analyzer |  | – | – | frequency_Hz=20–2000000; measurement_time_s=≤0.0056 | limited |
| [keysight-e4990a-impedance-analyzer](equipment/keysight/keysight-e4990a-impedance-analyzer.json) | 계열 | network_lcr_analyzer |  | – | – | frequency_Hz=20–120000000; impedance_ohm=0.025–40000000 | limited |
| [keysight-e4991b-impedance-analyzer](equipment/keysight/keysight-e4991b-impedance-analyzer.json) | 계열 | network_lcr_analyzer |  | – | – | frequency_Hz=1000000–3000000000; impedance_ohm=0.12–52000 | limited |
| [keysight-e7515a-uxm](equipment/keysight/keysight-e7515a-uxm.json) | 계열 | radio_communication_tester |  | – | – | radio_standards=LTE-Advanced Pro, LTE-U/LAA, W-CDMA, TD-SCDMA, GSM, IMS/VoLTE, WLAN calling/offload, Cat 1 | limited |
| [keysight-ena-vna](equipment/keysight/keysight-ena-vna.json) | 계열 | network_lcr_analyzer |  | – | – | frequency_Hz=9000–53000000000; rf_port_count=2, 4; dynamic_range_dB=≤140 | limited |
| [keysight-exg-x-series](equipment/keysight/keysight-exg-x-series.json) | 계열 | signal_generator |  | – | – | output_frequency_Hz=9000–40000000000; bandwidth_Hz=≤160000000; rf_output_level_dBm=≤23; phase_noise_dBc_Hz=-122; channels=1 | limited |
| [keysight-exm-e6640a](equipment/keysight/keysight-exm-e6640a.json) | 계열 | radio_communication_tester |  | – | – | frequency_Hz=≤6000000000; bandwidth_Hz=≤160000000; channels=1, 2, 3, 4; rf_port_count=≤8; radio_standards=5G NR, LTE/LTE-A (FDD/TDD), HSPA+, W-CDMA, 1xEV-DO, cd | limited |
| [keysight-infiniium-exr](equipment/keysight/keysight-infiniium-exr.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=500000000–2500000000; channels=4, 8; sample_rate_Sa_s=≤16000000000; record_length_pts=100000000–1600000000; adc_resolution_bit=10; logic_channel_co | limited |
| [keysight-infiniium-mxr](equipment/keysight/keysight-infiniium-mxr.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=500000000–6000000000; channels=4, 8; sample_rate_Sa_s=≤16000000000; record_length_pts=≤1600000000; adc_resolution_bit=10; logic_channel_count=16; d | limited |
| [keysight-infiniium-s-series](equipment/keysight/keysight-infiniium-s-series.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=2500000000–8000000000; sample_rate_Sa_s=≤20000000000; record_length_pts=≤100000000; channels=4; logic_channel_count=16; adc_resolution_bit=10; disp | limited |
| [keysight-infiniium-uxr](equipment/keysight/keysight-infiniium-uxr.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=13000000000–110000000000; sample_rate_Sa_s=128000000000–256000000000; record_length_pts=500000000–2000000000; channels=4; adc_resolution_bit=10 | limited |
| [keysight-infiniivision-1000x](equipment/keysight/keysight-infiniivision-1000x.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=50000000–200000000; sample_rate_Sa_s=1000000000–2000000000; record_length_pts=200000–2000000; channels=2, 4; adc_resolution_bit=8; display_size_in= | limited |
| [keysight-infiniivision-2000x](equipment/keysight/keysight-infiniivision-2000x.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=70000000–200000000; sample_rate_Sa_s=≤2000000000; record_length_pts=≤1000000; channels=2, 4; adc_resolution_bit=8; display_size_in=8.5 | limited |
| [keysight-infiniivision-3000g-x](equipment/keysight/keysight-infiniivision-3000g-x.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=100000000–1000000000; sample_rate_Sa_s=≤5000000000; record_length_pts=≤4000000; channels=2, 4; logic_channel_count=16; adc_resolution_bit=8; displa | limited |
| [keysight-infiniivision-3000t-x](equipment/keysight/keysight-infiniivision-3000t-x.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=100000000–1000000000; sample_rate_Sa_s=≤5000000000; channels=2, 4; logic_channel_count=16; display_size_in=8.5; record_length_pts=≤4000000 | limited |
| [keysight-infiniivision-4000x](equipment/keysight/keysight-infiniivision-4000x.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=200000000–1500000000; sample_rate_Sa_s=≤5000000000; record_length_pts=≤4000000; channels=2, 4; logic_channel_count=16; adc_resolution_bit=8; displa | limited |
| [keysight-infiniivision-6000x](equipment/keysight/keysight-infiniivision-6000x.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=1000000000–6000000000; sample_rate_Sa_s=≤20000000000; record_length_pts=≤4000000; channels=2, 4; logic_channel_count=16; adc_resolution_bit=8; disp | limited |
| [keysight-infiniivision-hd3](equipment/keysight/keysight-infiniivision-hd3.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=200000000–1000000000; sample_rate_Sa_s=≤3200000000; record_length_pts=≤100000000; channels=4; logic_channel_count=16; adc_resolution_bit=14; displa | limited |
| [keysight-mxg-n5185a-n5186a](equipment/keysight/keysight-mxg-n5185a-n5186a.json) | 계열 | signal_generator |  | – | – | output_frequency_Hz=9000–8500000000; bandwidth_Hz=≤1000000000; rf_output_level_dBm=≤25; phase_noise_dBc_Hz=-147, -146; channels=≤4 | limited |
| [keysight-mxg-x-series](equipment/keysight/keysight-mxg-x-series.json) | 계열 | signal_generator |  | – | – | output_frequency_Hz=9000–40000000000; bandwidth_Hz=≤160000000; rf_output_level_dBm=≤24; phase_noise_dBc_Hz=-146; channels=1 | limited |
| [keysight-n9048b-pxe](equipment/keysight/keysight-n9048b-pxe.json) | 계열 | emi_receiver | emi_emission | – | – | frequency_Hz=1–44000000000; resolution_bandwidth_Hz=10–1000000 | catalog |
| [keysight-pna](equipment/keysight/keysight-pna.json) | 계열 | network_lcr_analyzer |  | – | – | frequency_Hz=900–67000000000; rf_port_count=2, 4 | limited |
| [keysight-pna-l](equipment/keysight/keysight-pna-l.json) | 계열 | network_lcr_analyzer |  | – | – | frequency_Hz=300000–50000000000; rf_port_count=2, 4 | limited |
| [keysight-pna-x](equipment/keysight/keysight-pna-x.json) | 계열 | network_lcr_analyzer |  | – | – | frequency_Hz=900–67000000000; rf_port_count=2, 4 | catalog |
| [keysight-psg](equipment/keysight/keysight-psg.json) | 계열 | signal_generator |  | – | – | output_frequency_Hz=100000–67000000000; bandwidth_Hz=≤80000000; rf_output_level_dBm=≤30; phase_noise_dBc_Hz=-143; channels=1 | limited |
| [keysight-streamline-usb-vna](equipment/keysight/keysight-streamline-usb-vna.json) | 계열 | network_lcr_analyzer |  | – | – | frequency_Hz=9000–53000000000; rf_port_count=2, 4, 6; rf_output_level_dBm=≤10 | limited |
| [keysight-truevolt-dmm](equipment/keysight/keysight-truevolt-dmm.json) | 계열 | dmm_daq |  | – | – | dmm_resolution_digits=6.5, 7.5; data_rate_Hz=300–50000 | limited |
| [keysight-uxm-5g](equipment/keysight/keysight-uxm-5g.json) | 계열 | radio_communication_tester |  | – | – | frequency_Hz=380000000–15000000000; bandwidth_Hz=≤1600000000; rf_port_count=4, 8; radio_standards=5G NR, LTE, RedCap, NB-IoT, CAT-M, W-CDMA, GSM, C-V2X | limited |

## KIC Thermal (`kic`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [kic-sra-reflow-analyzer](equipment/kic/kic-sra-reflow-analyzer.json) | 기종 | thermal_profiler | thermal_profiling, solderability | – | – | profile_storage=≤30 | limited |

## Kikusui Electronics (`kikusui`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [kikusui-tos9300](equipment/kikusui/kikusui-tos9300.json) | 계열 | hipot_safety_analyzer | dielectric_withstand, insulation_resistance, ground_bond | – | – | ac_withstand_voltage_kV=≤5.0; dc_withstand_voltage_kV=≤7.2; insulation_resistance_ohm=1000–100000000000; leakage_current_A=1e-06–0.1; ground_bond_resistance_ohm | catalog |

## Kistler Group (`kistler`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [kistler-90x1c-ring-force-transducers](equipment/kistler/kistler-90x1c-ring-force-transducers.json) | **센서** | force_pressure_sensor |  | ≤1200 | – |  | limited |
| [kistler-910xc-industrial-ring-force-transducers](equipment/kistler/kistler-910xc-industrial-ring-force-transducers.json) | **센서** | force_pressure_sensor |  | ≤700 | – | operating_temperature_degC=-40–120 | limited |

## KLA Instruments (Nanomechanics) (`kla`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [kla-g200x](equipment/kla/kla-g200x.json) | 기종 | nanoindenter | instrumented_indentation, fatigue | – | ≤300.0 |  | catalog |
| [kla-imicro](equipment/kla/kla-imicro.json) | 기종 | instrumented_indentation | instrumented_indentation, friction_wear_tribo, dma | – | ≤300 | indentation_force_mN=≤1000; data_rate_Hz=≤100000 | catalog |
| [kla-imicro-materialtwin](equipment/kla/kla-imicro-materialtwin.json) | 계열 (보탬→kla-imicro) | instrumented_indentation | instrumented_indentation, friction_wear_tribo, dma | – | – |  | catalog |
| [kla-tencor-p-7](equipment/kla/kla-tencor-p-7.json) | 기종 | optical_profilometer | surface_topography | – | – |  | catalog |

## KLIPPEL GmbH (`klippel`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [klippel-rd-system-analyzers](equipment/klippel/klippel-rd-system-analyzers.json) | 계열 | acoustic_measurement | audio_performance | – | – | data_rate_Hz=48000–192000; adc_resolution_bit=24 | limited |

## Konica Minolta Sensing (`konica-minolta`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [konica-minolta-ca-2500](equipment/konica-minolta/konica-minolta-ca-2500.json) | 계열 | imaging_colorimeter | photometry_colorimetry | – | – | luminance_cd_m2=0.05–100000; resolution_pixels=≤1000000 | catalog |
| [konica-minolta-ca-310](equipment/konica-minolta/konica-minolta-ca-310.json) | 계열 | display_color_analyzer | photometry_colorimetry | – | – |  | limited |
| [konica-minolta-ca-410](equipment/konica-minolta/konica-minolta-ca-410.json) | 계열 | display_color_analyzer | photometry_colorimetry | – | – | luminance_cd_m2=0.002–12000; acceptance_angle_deg=4–10; measurement_distance_mm=28–200 | catalog |
| [konica-minolta-ca-510](equipment/konica-minolta/konica-minolta-ca-510.json) | 계열 | display_color_analyzer | photometry_colorimetry | – | – | luminance_cd_m2=0.0002–20000; acceptance_angle_deg=15; spot_diameter_mm=10; measurement_distance_mm=25–35 | catalog |
| [konica-minolta-ca-527](equipment/konica-minolta/konica-minolta-ca-527.json) | 계열 | display_color_analyzer | photometry_colorimetry | – | – | luminance_cd_m2=0.0001–10000; spot_diameter_mm=27; acceptance_angle_deg=8.5; measurement_distance_mm=25–35; luminance_accuracy_pct=1.5–9; chromaticity_accuracy_ | catalog |
| [konica-minolta-cl-200a](equipment/konica-minolta/konica-minolta-cl-200a.json) | 계열 | display_color_analyzer | photometry_colorimetry | – | – | illuminance_lx=0.1–99990 | catalog |
| [konica-minolta-cl-500a](equipment/konica-minolta/konica-minolta-cl-500a.json) | 계열 | spectroradiometer | photometry_colorimetry | – | – | wavelength_nm=360–780; illuminance_lx=0.1–100000 | catalog |
| [konica-minolta-cs-150-160](equipment/konica-minolta/konica-minolta-cs-150-160.json) | 계열 | display_color_analyzer | photometry_colorimetry | – | – | luminance_cd_m2=0.01–9999000; acceptance_angle_deg=1, 0.33; measurement_distance_mm=≥213 | catalog |
| [konica-minolta-cs-200](equipment/konica-minolta/konica-minolta-cs-200.json) | 계열 | display_color_analyzer | photometry_colorimetry | – | – | luminance_cd_m2=0.01–20000000; measuring_angle_deg=1, 0.2, 0.1; spot_diameter_mm=≥0.1 | catalog |
| [konica-minolta-cs-2000](equipment/konica-minolta/konica-minolta-cs-2000.json) | 계열 | spectroradiometer | photometry_colorimetry | – | – | luminance_cd_m2=0.0005–50000000; illuminance_lx=1.0–7500000; spectral_bandwidth_nm=≤5; measuring_angle_deg=1, 0.2, 0.1; polarization_error_pct=≤2 | catalog |
| [konica-minolta-cs-3000](equipment/konica-minolta/konica-minolta-cs-3000.json) | 계열 | spectroradiometer | photometry_colorimetry | – | – | wavelength_nm=380–780; spectral_bandwidth_nm=≤5; measuring_angle_deg=1, 0.2, 0.1; luminance_cd_m2=0.0001–10000000 | catalog |
| [konica-minolta-ls-150-160](equipment/konica-minolta/konica-minolta-ls-150-160.json) | 계열 | display_color_analyzer | photometry_colorimetry | – | – | luminance_cd_m2=0.001–9999000; acceptance_angle_deg=1, 0.33 | catalog |

## KRÜSS (`kruss`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [kruss-dsa100hp](equipment/kruss/kruss-dsa100hp.json) | 계열 | contact_angle_analyzer | contact_angle | – | 20.0–250.0 |  | catalog |

## L.A.B. Equipment, Inc. (`lab-equipment`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [lab-equipment-autoshock-ii](equipment/lab-equipment/lab-equipment-autoshock-ii.json) | 계열 | shock_test_machine | mechanical_shock | – | – | acceleration_g=≤600; pulse_duration_ms=2.0–65; velocity_change_m_s=7.0–12.2; payload_kg=600–900; table_size_mm=610–1520 | limited |
| [lab-equipment-incline-impact-testers](equipment/lab-equipment/lab-equipment-incline-impact-testers.json) | 계열 | shock_test_machine | mechanical_shock | – | – | payload_kg=454–4536; impact_velocity_m_s=2.44 | limited |
| [lab-equipment-sd-series-shock](equipment/lab-equipment/lab-equipment-sd-series-shock.json) | 계열 | shock_test_machine | mechanical_shock | – | – | acceleration_g=1000–3500; pulse_duration_ms=≥0.3; payload_kg=14–181; table_size_mm=254, 406, 610; drop_height_mm=1067, 1524 | limited |
| [lab-equipment-truedrop-drop-testers](equipment/lab-equipment/lab-equipment-truedrop-drop-testers.json) | 계열 | drop_tester | free_fall_drop | – | – | payload_kg=≤73; drop_height_mm=305–1829 | limited |
| [lab-equipment-vibratest](equipment/lab-equipment/lab-equipment-vibratest.json) | 계열 | mechanical_dynamics | vibration_sine_random | – | – | frequency_Hz=8–60; acceleration_g=3.2, 10; payload_kg=45–227; displacement_mm=1.3–2.2; table_size_mm=610–1676 | limited |

## Lake Shore Cryotronics (`lake-shore`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [lake-shore-hms](equipment/lake-shore/lake-shore-hms.json) | 계열 | electrical_property_tester | electrical_transport | – | -271.15–526.85 |  | catalog |

## Lansmont Corporation (`lansmont`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [lansmont-hc-high-cycle-shock-test-systems](equipment/lansmont/lansmont-hc-high-cycle-shock-test-systems.json) | 계열 | shock_test_machine | mechanical_shock | – | – | acceleration_g=≤5000; pulse_duration_ms=0.3–2; velocity_change_m_s=8.38; payload_kg=≤9; cycle_rate_cpm=≤50; table_size_mm=180, 230 | limited |
| [lansmont-hs-hsx-high-speed-shock-test-systems](equipment/lansmont/lansmont-hs-hsx-high-speed-shock-test-systems.json) | 계열 | shock_test_machine | mechanical_shock | – | – | acceleration_g=≤10000; pulse_duration_ms=≥0.2; velocity_change_m_s=≤45.8; payload_kg=≤907; table_size_mm=100–600 | limited |
| [lansmont-hydraulic-vibration-test-systems](equipment/lansmont/lansmont-hydraulic-vibration-test-systems.json) | 계열 | mechanical_dynamics | vibration_sine_random | – | – | static_force_kN=5.4–283.4; dynamic_force_kN=3.6–189; frequency_Hz=1–500; table_size_mm=400–4060 | limited |
| [lansmont-inclined-impact-testers](equipment/lansmont/lansmont-inclined-impact-testers.json) | 계열 | shock_test_machine | mechanical_shock | – | – | payload_kg=1814–2721; impact_velocity_m_s=≤2.2; table_size_mm=1520, 2130 | limited |
| [lansmont-model-15-23-shock-test-systems](equipment/lansmont/lansmont-model-15-23-shock-test-systems.json) | 계열 | shock_test_machine | mechanical_shock | – | – | acceleration_g=≤10000; pulse_duration_ms=≥0.25; velocity_change_m_s=7.3–9.7; payload_kg=≤36; table_size_mm=230 | limited |
| [lansmont-model-23c-cushion-tester](equipment/lansmont/lansmont-model-23c-cushion-tester.json) | 기종 | shock_test_machine |  | – | – |  | limited |
| [lansmont-ms-mechanical-shakers](equipment/lansmont/lansmont-ms-mechanical-shakers.json) | 계열 | mechanical_dynamics | vibration_sine_random | – | – | payload_kg=181–907; frequency_Hz=2–5; displacement_mm=25.4; table_size_mm=1220, 1520 | limited |
| [lansmont-pdt-drop-testers](equipment/lansmont/lansmont-pdt-drop-testers.json) | 계열 | drop_tester | free_fall_drop | – | – | payload_kg=≤80; drop_height_mm=25–1830; package_size_mm=≤915 | catalog |
| [lansmont-pdt-drop-testers-web](equipment/lansmont/lansmont-pdt-drop-testers-web.json) | 계열 (보탬→lansmont-pdt-drop-testers) | drop_tester | free_fall_drop | – | – |  | limited |
| [lansmont-qr-3000-drop-tester](equipment/lansmont/lansmont-qr-3000-drop-tester.json) | 기종 | drop_tester | free_fall_drop | – | – | payload_kg=11–1361 | limited |
| [lansmont-saver-field-data-recorders](equipment/lansmont/lansmont-saver-field-data-recorders.json) | 계열 | mechanical_dynamics |  | – | – | acceleration_g=5, 10, 20, 50, 100, 200; data_rate_Hz=50–10000; channels=3, 9; adc_resolution_bit=16; operating_temperature_degC=-40–60 | limited |
| [lansmont-shock-test-systems](equipment/lansmont/lansmont-shock-test-systems.json) | 계열 | shock_test_machine | mechanical_shock, free_fall_drop | – | – | acceleration_g=1000–10000; pulse_duration_ms=≥0.25; velocity_change_m_s=6.1–18; payload_kg=50–1134; table_size_mm=230–1220 | catalog |
| [lansmont-shock-test-systems-web](equipment/lansmont/lansmont-shock-test-systems-web.json) | 계열 (보탬→lansmont-shock-test-systems) | shock_test_machine | mechanical_shock | – | – |  | limited |

## LaVision GmbH (`lavision`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [lavision-strainmaster](equipment/lavision/lavision-strainmaster.json) | 계열 | dic_strain_measurement | tensile, compression, fatigue | – | – | detector_megapixels=1–25; data_rate_Hz=22–300000; field_of_view_mm=20–2000; strain_resolution_microstrain=50 | catalog |

## Leica Microsystems (`leica-microsystems`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [leica-microsystems-dm2700-m](equipment/leica-microsystems/leica-microsystems-dm2700-m.json) | 기종 | optical_microscope | microscopy | – | – | sample_size_mm=≤100; specimen_height_mm=≤80; magnification=0.7–100 | limited |
| [leica-microsystems-dm8000-m-dm12000-m](equipment/leica-microsystems/leica-microsystems-dm8000-m-dm12000-m.json) | 계열 | optical_microscope | microscopy | – | – | wafer_size_mm=200, 300; specimen_height_mm=≤42; magnification=0.7–150 | limited |
| [leica-microsystems-dvm6](equipment/leica-microsystems/leica-microsystems-dvm6.json) | 계열 | optical_microscope | microscopy | – | – | zoom_ratio=16; magnification=≤2350; field_of_view_mm=≤43.75; working_distance_mm=5–60; optical_resolution_lp_mm=415–2366; tilt_angle_deg=-60–60; stage_travel_mm | limited |
| [leica-microsystems-emspira-3](equipment/leica-microsystems/leica-microsystems-emspira-3.json) | 기종 | optical_microscope | microscopy | – | – | zoom_ratio=8; field_of_view_mm=≤76.1; working_distance_mm=19–303; data_rate_Hz=≤60; detector_megapixels=12; magnification=8.2–1027; optical_resolution_lp_mm=≤33 | catalog |

## Xi'an LIB Environmental Simulation Industry (`lib-industry`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [lib-industry-ipx9k-test-device](equipment/lib-industry/lib-industry-ipx9k-test-device.json) | 계열 | water_ingress_tester | water_ingress | – | – | ipx_levels=–; water_pressure_bar=80–100; spray_flow_L_min=14–16; water_temperature_degC=≤88; turntable_speed_rpm=5; turntable_diameter_mm=≤600; chamber_volume_L | limited |

## QMESYS (큐머시스) (`limotem`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [qmesys-qm100](equipment/limotem/qmesys-qm100.json) | 계열 | universal_testing_machine | tensile, compression, flexure, peel, tear, friction_coefficient, shear | 0.049–294 | – | crosshead_speed_mm_min=0.1–600; crosshead_travel_mm=450–1100; horizontal_test_space_mm=350–660 | catalog |

## LINSEIS (`linseis`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [linseis-chip-dsc-l66](equipment/linseis/linseis-chip-dsc-l66.json) | 계열 | dsc | dsc | – | -180–600 | heating_rate_K_min=0.001–1000 | catalog |
| [linseis-dil-l74-optical](equipment/linseis/linseis-dil-l74-optical.json) | 계열 | dilatometer | dilatometry | – | -100–2000 |  | limited |
| [linseis-dil-l75-l76](equipment/linseis/linseis-dil-l75-l76.json) | 계열 | dilatometer | dilatometry | – | -263–2800 |  | limited |
| [linseis-dil-l78-rita](equipment/linseis/linseis-dil-l78-rita.json) | 계열 | dilatometer | dilatometry | ≤22 | -150–1600 |  | catalog |
| [linseis-dsc-l63](equipment/linseis/linseis-dsc-l63.json) | 계열 | dsc | dsc | – | -170–750 | heating_rate_K_min=0.01–200; cooling_rate_K_min=≤100 | catalog |
| [linseis-hdsc-l62](equipment/linseis/linseis-hdsc-l62.json) | 계열 | dsc | dsc | – | -150–1750 | heating_rate_K_min=0.01–100 | catalog |
| [linseis-sta](equipment/linseis/linseis-sta.json) | 계열 | sta | tga, dsc, dilatometry | – | -150–2800 | pressure_bar=≤150 | limited |
| [linseis-tga](equipment/linseis/linseis-tga.json) | 계열 | tga | tga | – | -196–2400 | pressure_bar=≤350 | limited |
| [linseis-thermal-conductivity](equipment/linseis/linseis-thermal-conductivity.json) | 계열 | thermal_conductivity | thermal_conductivity | – | -170–2800 | thermal_diffusivity_mm2_s=0.01–1000; thermal_conductivity_W_mK=0.1–2000; heating_rate_K_min=≤300 | catalog |
| [linseis-tma-l71-l72](equipment/linseis/linseis-tma-l71-l72.json) | 계열 | tma | tma, dma, creep, relaxation, dilatometry | – | -180–2400 | force_N=0.001–20; frequency_Hz=0.01–50; heating_rate_K_min=0.1–100; sample_length_mm=20–50; specimen_diameter_mm=≤10 | catalog |
| [linseis-udsc-l64](equipment/linseis/linseis-udsc-l64.json) | 계열 | dsc | dsc | – | -170–160 | sample_volume_uL=5–100 | limited |

## Listen, Inc. (`listen-inc`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [listen-inc-audio-interfaces](equipment/listen-inc/listen-inc-audio-interfaces.json) | 계열 | acoustic_measurement | audio_performance | – | – | data_rate_Hz=≤192000; channels=2, 6, 8 | limited |
| [listen-inc-scm-measurement-microphones](equipment/listen-inc/listen-inc-scm-measurement-microphones.json) | **센서** | acoustic_measurement |  | – | – | frequency_Hz=20–20000; sound_pressure_level_dB=23–134; mic_sensitivity_mV_Pa=20 | limited |
| [listen-inc-soundcheck](equipment/listen-inc/listen-inc-soundcheck.json) | software | acoustic_measurement | audio_performance | – | – | channels=≤64 | limited |

## LitePoint (`litepoint`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [litepoint-iqxel-mw-7g](equipment/litepoint/litepoint-iqxel-mw-7g.json) | 계열 | radio_communication_tester |  | – | – | frequency_Hz=400000000–7300000000; bandwidth_Hz=≤160000000; rf_port_count=2, 4, 8, 16; radio_standards=802.11a/b/g/j/n/p, 802.11ac, 802.11ax (Wi-Fi 6/6E), 802.1 | limited |
| [litepoint-iqxstream-5g](equipment/litepoint/litepoint-iqxstream-5g.json) | 계열 | radio_communication_tester |  | – | – | frequency_Hz=400000000–7300000000; bandwidth_Hz=≤200000000; rf_output_level_dBm=≤5; rf_port_count=≤32; radio_standards=5G NR FR1, LTE TDD/FDD, C-V2X, LAA, 2G/3G | limited |

## Maccor (`maccor`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [maccor-series-4000](equipment/maccor/maccor-series-4000.json) | 계열 | battery_cycler | battery_cycle_life | – | – | voltage_V=-2–8; current_A=0.00015–20; channels=–; fra_frequency_Hz=≥0.001; fra_current_A=≤3.0; fra_voltage_V=≤55 | catalog |

## Malcom Co., Ltd. (`malcom`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [malcom-wetting-testers](equipment/malcom/malcom-wetting-testers.json) | 계열 | solderability_tester | solderability | – | ≤400 | wetting_force_mN=-49.03–98.07; dip_depth_mm=0.01–20; dip_speed_mm_s=0.1–30; test_time_s=1–200 | limited |

## Malvern Panalytical (`malvern-panalytical`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [malvern-kinexus](equipment/malvern-panalytical/malvern-kinexus.json) | 계열 | rotational_rheometer | rheology_rotational | – | -40–200 | torque_mNm=5e-07–250; angular_velocity_rad_s=1e-08–500; frequency_Hz=1e-06–150; force_N=0.001–50 | catalog |
| [malvern-kinexus-materialtwin](equipment/malvern-panalytical/malvern-kinexus-materialtwin.json) | 계열 (보탬→malvern-kinexus) | rotational_rheometer | rheology_rotational, shear | – | – |  | catalog |
| [malvern-mastersizer-3000](equipment/malvern-panalytical/malvern-mastersizer-3000.json) | 기종 | particle_size_analyzer | particle_size | – | – |  | catalog |
| [malvern-zetasizer-nano-zsp](equipment/malvern-panalytical/malvern-zetasizer-nano-zsp.json) | 기종 | particle_size_analyzer | particle_size | – | – |  | catalog |

## Mark-10 Corporation (`mark-10`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [mark-10-series-5-force-gauges](equipment/mark-10/mark-10-series-5-force-gauges.json) | 계열 | force_pressure_sensor | tensile, compression | – | – | force_N=0.5–10000; digital_sample_rate_Hz=≤7000; data_rate_Hz=≤500; operating_temperature_degC=4.4–37.8 | catalog |
| [mark-10-series-7-force-gauges](equipment/mark-10/mark-10-series-7-force-gauges.json) | 계열 | force_pressure_sensor | tensile, compression | – | – | force_N=0.5–2500; digital_sample_rate_Hz=≤14000; data_rate_Hz=≤250; operating_temperature_degC=4.4–37.8 | catalog |
| [mark-10-series-f-force-testers](equipment/mark-10/mark-10-series-f-force-testers.json) | 계열 | force_tester | tensile, compression | 0.5–6.7 | – | crosshead_speed_mm_min=0.02–1800; crosshead_travel_mm=≤813; digital_sample_rate_Hz=≤20000; operating_temperature_degC=5–35; data_rate_Hz=≤1000 | catalog |

## Mecmesin (`mecmesin`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [mecmesin-adapters-qc-fittings-and-extension-rods](equipment/mecmesin/mecmesin-adapters-qc-fittings-and-extension-rods.json) | **부속** | accessory | tensile, compression | 0.5–25 | – |  | limited |
| [mecmesin-compression-plates](equipment/mecmesin/mecmesin-compression-plates.json) | **부속** | grip_fixture | compression | ≤50 | – | specimen_diameter_mm=12–196; width_mm=50–596 | limited |
| [mecmesin-gauge-and-stand-accessories](equipment/mecmesin/mecmesin-gauge-and-stand-accessories.json) | **부속** | accessory | tensile, compression, torsion | – | – |  | limited |
| [mecmesin-grips](equipment/mecmesin/mecmesin-grips.json) | **부속** | grip_fixture | tensile, peel | – | – | force_N=50–10000; test_opening_mm=≤52 | limited |
| [mecmesin-multitest](equipment/mecmesin/mecmesin-multitest.json) | 계열 | force_tester | tensile, compression, peel, flexure, friction_coefficient | 0.002–50 | – | crosshead_speed_mm_min=0.1–1200; crosshead_travel_mm=500–1200 | catalog |
| [mecmesin-omnitest](equipment/mecmesin/mecmesin-omnitest.json) | 계열 | universal_testing_machine | tensile, compression, flexure, shear, peel, tear, friction_coefficient | 0.002–50 | – | crosshead_speed_mm_min=0.01–500; crosshead_travel_mm=507–1230; horizontal_test_space_mm=420, 425; data_rate_Hz=≤1000 | catalog |
| [mecmesin-test-fixtures](equipment/mecmesin/mecmesin-test-fixtures.json) | **부속** | grip_fixture | flexure, friction_coefficient, peel, tensile, shear, puncture, compression | 0.05–25 | – |  | limited |

## Memmert GmbH + Co. KG (`memmert`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [memmert-hcp](equipment/memmert/memmert-hcp.json) | 계열 | climatic_chamber | damp_heat | – | ≤90 | humidity_pct=20–95; chamber_volume_L=56–241 | limited |
| [memmert-hppeco](equipment/memmert/memmert-hppeco.json) | 계열 | climatic_chamber | damp_heat | – | 0–70 | humidity_pct=10–90; chamber_volume_L=108–2140 | limited |
| [memmert-ich](equipment/memmert/memmert-ich.json) | 계열 | climatic_chamber | damp_heat | – | -10–60 | humidity_pct=10–80; chamber_volume_L=108–749 | limited |
| [memmert-testa](equipment/memmert/memmert-testa.json) | 계열 | climatic_chamber | damp_heat, temperature_cycling | – | -75–180 | humidity_pct=10–98; heating_rate_K_min=≤10; cooling_rate_K_min=≤10; chamber_volume_L=272–967 | limited |

## Metrohm (`metrohm`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [metrohm-851-titrando](equipment/metrohm/metrohm-851-titrando.json) | 기종 | karl_fischer_titrator | water_content | – | – |  | catalog |

## METTLER TOLEDO (`mettler-toledo`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [mettler-dma-sdta861e](equipment/mettler-toledo/mettler-dma-sdta861e.json) | 기종 | dma | dma | – | -150–500 | force_N=0.001–40; frequency_Hz=0.001–1000; displacement_um=≤1600; sample_length_mm=≤100 | catalog |
| [mettler-tga-dsc-1](equipment/mettler-toledo/mettler-tga-dsc-1.json) | 계열 | sta | tga, dsc | – | 20–1600 | heating_rate_K_min=≤250; sample_mass_mg=≤5000; balance_resolution_ug=≥0.1; sample_volume_uL=≤900 | catalog |
| [mettler-toledo-dma-1](equipment/mettler-toledo/mettler-toledo-dma-1.json) | 계열 | dma | dma | – | -190–600 | frequency_Hz=0.001–300 | limited |
| [mettler-toledo-dsc-3](equipment/mettler-toledo/mettler-toledo-dsc-3.json) | 계열 | dsc | dsc | – | -150.0–700.0 |  | limited |
| [mettler-toledo-dsc-5-plus](equipment/mettler-toledo/mettler-toledo-dsc-5-plus.json) | 계열 | dsc | dsc | – | -150–700 |  | limited |
| [mettler-toledo-flash-dsc-2-plus](equipment/mettler-toledo/mettler-toledo-flash-dsc-2-plus.json) | 계열 | dsc | dsc | – | -95–1000 | heating_rate_K_min=6–3000000 | limited |
| [mettler-toledo-tga-2](equipment/mettler-toledo/mettler-toledo-tga-2.json) | 계열 | tga | tga | – | – |  | limited |
| [mettler-toledo-tga-dsc-3-plus](equipment/mettler-toledo/mettler-toledo-tga-dsc-3-plus.json) | 계열 | sta | tga, dsc | – | ≤1600 |  | limited |
| [mettler-toledo-tma-sdta-2-plus](equipment/mettler-toledo/mettler-toledo-tma-sdta-2-plus.json) | 계열 | tma | tma | – | -150–1600 |  | limited |

## Micro-Epsilon (`micro-epsilon`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [micro-epsilon-capancdt-6200](equipment/micro-epsilon/micro-epsilon-capancdt-6200.json) | 계열 | thickness_displacement_gauge |  | – | – | measurement_channels=≤4; bandwidth_Hz=≤20000; data_rate_Hz=≤3900 | limited |
| [micro-epsilon-confocaldt](equipment/micro-epsilon/micro-epsilon-confocaldt.json) | 계열 | thickness_displacement_gauge |  | – | – | displacement_mm=0.3–30; linearity_um=≥0.09; position_resolution_nm=≥2; data_rate_Hz=≤30000; measurement_distance_mm=6–220; spot_size_um=6–60 | catalog |
| [micro-epsilon-interferometer](equipment/micro-epsilon/micro-epsilon-interferometer.json) | 계열 | thickness_displacement_gauge |  | – | – | displacement_mm=1–2.1; layer_thickness_um=1–4000; linearity_um=0.01–0.2; position_resolution_nm=≥0.03; data_rate_Hz=≤6000 | limited |
| [micro-epsilon-optoncdt-1420](equipment/micro-epsilon/micro-epsilon-optoncdt-1420.json) | 계열 | thickness_displacement_gauge |  | – | – | displacement_mm=10–500; linearity_um=≥8; measuring_repeatability_um=≥0.5; data_rate_Hz=≤8000; measurement_distance_mm=20–100; laser_wavelength_nm=670; operating | catalog |
| [micro-epsilon-optoncdt-2300](equipment/micro-epsilon/micro-epsilon-optoncdt-2300.json) | 계열 | thickness_displacement_gauge |  | – | – | displacement_mm=2–300; linearity_um=≥0.6; position_resolution_nm=≥30; data_rate_Hz=≤49140; measurement_distance_mm=24–550; laser_wavelength_nm=670, 405; operati | catalog |

## Micromeritics (`micromeritics`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [micromeritics-accupyc-autopore-accessories](equipment/micromeritics/micromeritics-accupyc-autopore-accessories.json) | **부속** | accessory | density_porosity | – | – |  | limited |
| [micromeritics-accupyc-ii-1345](equipment/micromeritics/micromeritics-accupyc-ii-1345.json) | 기종 | pycnometer_porosimeter | density_porosity | – | 15.0–50.0 |  | catalog |
| [micromeritics-autopore-v](equipment/micromeritics/micromeritics-autopore-v.json) | 기종 | pycnometer_porosimeter | instrumented_indentation | – | – |  | catalog |

## Mitutoyo (`mitutoyo`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [mitutoyo-abk-1](equipment/mitutoyo/mitutoyo-abk-1.json) | 기종 | brinell_hardness | hardness_brinell | – | – |  | catalog |
| [mitutoyo-ar-atk-rockwell](equipment/mitutoyo/mitutoyo-ar-atk-rockwell.json) | 계열 | rockwell_hardness | hardness_rockwell | – | – |  | catalog |
| [mitutoyo-avk](equipment/mitutoyo/mitutoyo-avk.json) | 계열 | vickers_knoop_hardness | hardness_vickers | – | ≤1200.0 |  | catalog |
| [mitutoyo-crysta-apex-v](equipment/mitutoyo/mitutoyo-crysta-apex-v.json) | 계열 | coordinate_measuring_machine |  | – | – | measuring_range_x_mm=500–1200; measuring_range_y_mm=400–2000; measuring_range_z_mm=400–1000; measuring_speed_mm_s=≤8 | catalog |
| [mitutoyo-crysta-plus-m](equipment/mitutoyo/mitutoyo-crysta-plus-m.json) | 계열 | coordinate_measuring_machine |  | – | – | measuring_range_x_mm=400–700; measuring_range_y_mm=400–1000; measuring_range_z_mm=300–600 | catalog |
| [mitutoyo-hardmatic-ud-410-leeb](equipment/mitutoyo/mitutoyo-hardmatic-ud-410-leeb.json) | 계열 | portable_hardness | hardness_leeb | – | – | hardness_scales=HLD, HLDC, HLD+15, HLDL | limited |
| [mitutoyo-hh-300-durometer](equipment/mitutoyo/mitutoyo-hh-300-durometer.json) | 계열 | shore_irhd_hardness | hardness_shore | – | – |  | catalog |
| [mitutoyo-hm-200](equipment/mitutoyo/mitutoyo-hm-200.json) | 계열 | vickers_knoop_hardness | hardness_vickers, hardness_knoop | – | – |  | catalog |
| [mitutoyo-hm-micro-vickers](equipment/mitutoyo/mitutoyo-hm-micro-vickers.json) | 계열 | vickers_knoop_hardness | hardness_vickers, hardness_knoop | – | – | test_load_gf=0.05–2000; hardness_scales=HV, HK; specimen_height_mm=≤133; specimen_depth_mm=≤160 | catalog |
| [mitutoyo-hm-micro-vickers-materialtwin](equipment/mitutoyo/mitutoyo-hm-micro-vickers-materialtwin.json) | 계열 (보탬→mitutoyo-hm-micro-vickers) | vickers_knoop_hardness | hardness_vickers, hardness_knoop | – | – |  | catalog |
| [mitutoyo-hr-500](equipment/mitutoyo/mitutoyo-hr-500.json) | 계열 | rockwell_hardness | hardness_rockwell | – | – |  | catalog |
| [mitutoyo-hr-600](equipment/mitutoyo/mitutoyo-hr-600.json) | 계열 | rockwell_hardness | hardness_rockwell | – | – |  | catalog |
| [mitutoyo-hr-series-rockwell](equipment/mitutoyo/mitutoyo-hr-series-rockwell.json) | 계열 | rockwell_hardness | hardness_rockwell, hardness_brinell | – | – | test_load_kgf=6.25–187.5; hardness_scales=HRA, HRB, HRC, HRD, HRE, HRF, HRG, HRH; specimen_height_mm=≤395; specimen_depth_mm=≤165 | catalog |
| [mitutoyo-hr-series-rockwell-materialtwin](equipment/mitutoyo/mitutoyo-hr-series-rockwell-materialtwin.json) | 계열 (보탬→mitutoyo-hr-series-rockwell) | rockwell_hardness | hardness_rockwell, hardness_brinell | – | – |  | catalog |
| [mitutoyo-hv-100](equipment/mitutoyo/mitutoyo-hv-100.json) | 계열 | vickers_knoop_hardness | hardness_vickers, fatigue, hardness_knoop, hardness_brinell | – | – |  | catalog |
| [mitutoyo-linear-height-lh-600](equipment/mitutoyo/mitutoyo-linear-height-lh-600.json) | 계열 | thickness_displacement_gauge |  | – | – |  | limited |
| [mitutoyo-litematic-vl-50](equipment/mitutoyo/mitutoyo-litematic-vl-50.json) | 계열 | thickness_displacement_gauge |  | – | – | displacement_mm=0–50; stylus_force_mN=10–1000; displacement_resolution_nm=≥10 | catalog |
| [mitutoyo-mzt-500](equipment/mitutoyo/mitutoyo-mzt-500.json) | 기종 | instrumented_indentation | instrumented_indentation | – | – |  | catalog |
| [mitutoyo-quick-vision-apex-pro](equipment/mitutoyo/mitutoyo-quick-vision-apex-pro.json) | 계열 | coordinate_measuring_machine |  | – | – | measuring_range_x_mm=300–600; measuring_range_y_mm=200–650; measuring_range_z_mm=200–250; position_resolution_nm=100; magnification=16–4800; field_of_view_mm=0. | catalog |
| [mitutoyo-surftest-sj-410](equipment/mitutoyo/mitutoyo-surftest-sj-410.json) | 계열 | surface_roughness_tester | surface_topography | – | – |  | catalog |
| [mitutoyo-thickness-gauge-547](equipment/mitutoyo/mitutoyo-thickness-gauge-547.json) | 계열 | thickness_displacement_gauge |  | – | – | specimen_thickness_mm=0–12 | limited |

## Molex (`molex`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [molex-crimp-pull-tester](equipment/molex/molex-crimp-pull-tester.json) | 기종 | crimp_pull_tester | crimp_pull_strength | – | – | pull_force_N=≤890; wire_cross_section_mm2=0.05–5.0 | catalog |

## MTDI (엠티디아이) (`mtdi`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [mtdi-circumference-tensile-tester](equipment/mtdi/mtdi-circumference-tensile-tester.json) | 계열 | burst_pressure_tester | burst_pressure, tensile | – | – | pressure_bar=≤1000; power_kW=0.15–23.8 | limited |
| [mtdi-electrolytic-etching-machine](equipment/mtdi/mtdi-electrolytic-etching-machine.json) | 계열 | electrolytic_etcher | surface_topography | – | – | voltage_V=0–30; weight_kg=27 | limited |
| [mtdi-fld-300s](equipment/mtdi/mtdi-fld-300s.json) | 계열 | formability_tester | formability, tensile | 981, 1961, 2942 | ≤900 | crosshead_travel_mm=≤200; crosshead_speed_mm_min=≤250; pressure_bar=≤210; data_rate_Hz=≤250000; power_kW=22 | catalog |
| [mtdi-specimen-preparation](equipment/mtdi/mtdi-specimen-preparation.json) | 계열 | cutting_mounting_polishing | surface_topography | – | ≤200 | rotation_rpm=50–5000; specimen_max_mm=≤80; pressure_bar=≤210; power_kW=0.18–11; weight_kg=24–600 | limited |
| [mtdi-torsion-tester](equipment/mtdi/mtdi-torsion-tester.json) | 계열 | torsion_tester | torsion, tensile, fatigue | ≤98 | -170–1100 | torque_Nm=≤981; rotation_rpm=0.1–1500; rotation_deg=≤360; crosshead_speed_mm_min=0.001–500; data_rate_Hz=≤100000; power_kW=45 | catalog |
| [mtdi-uc-furnace-chambers](equipment/mtdi/mtdi-uc-furnace-chambers.json) | **부속** | furnace | tensile, compression, creep | – | -170–1100 | chamber_volume_L=– | catalog |
| [mtdi-wear-friction-testers](equipment/mtdi/mtdi-wear-friction-testers.json) | 계열 | tribometer | friction_coefficient, friction_wear_tribo, abrasion | – | ≤1100 | force_N=≤100000; rotation_rpm=1–15000; frequency_Hz=0.1–5; sliding_speed_m_s=–; torque_Nm=≤50; data_rate_Hz=≤250000; power_kW=1.5–13 | catalog |

## MTS Systems (`mts`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [mts-632-79-immersible-extensometer](equipment/mts/mts-632-79-immersible-extensometer.json) | **센서** | extensometer | tensile, fatigue, flexure | – | -15–85 | gauge_length_mm=25–200; frequency_Hz=≤30 | limited |
| [mts-632-averaging-biaxial-transverse-diametral-extensometers](equipment/mts/mts-632-averaging-biaxial-transverse-diametral-extensometers.json) | **센서** | extensometer | tensile, compression, fatigue | – | -265–150 | gauge_length_mm=10–25; specimen_diameter_mm=2–32; width_mm=≤51 | limited |
| [mts-632-axial-extensometers-small-gauge-and-enhanced-travel](equipment/mts/mts-632-axial-extensometers-small-gauge-and-enhanced-travel.json) | **센서** | extensometer | tensile, fatigue, flexure | – | -269–175 | gauge_length_mm=3–50; frequency_Hz=≤150 | limited |
| [mts-632-clip-on-and-displacement-gages](equipment/mts/mts-632-clip-on-and-displacement-gages.json) | **센서** | extensometer | fracture_toughness, fatigue, flexure | – | -100–175 | gauge_length_mm=2–12; displacement_mm=≤6; frequency_Hz=≤100 | limited |
| [mts-634-axial-extensometers](equipment/mts/mts-634-axial-extensometers.json) | **센서** | extensometer | tensile, flexure, fatigue | – | -269–175 | gauge_length_mm=25–200 | limited |
| [mts-650-03-extensometer-calibrator](equipment/mts/mts-650-03-extensometer-calibrator.json) | **부속** | accessory |  | – | – | displacement_um=≥0.5 | limited |
| [mts-acumen](equipment/mts/mts-acumen.json) | 계열 | electrodynamic_fatigue | fatigue, tensile, compression, flexure, torsion, dma | – | – | dynamic_force_kN=1.25–12; static_force_kN=1–8.5; torque_Nm=30, 120; stroke_mm=70; rotation_deg=≤135; frequency_Hz=≤100; vertical_test_space_mm=0–985; horizontal | catalog |
| [mts-advantage-mini-grips](equipment/mts/mts-advantage-mini-grips.json) | **부속** | grip_fixture | tensile, fatigue | – | – | static_force_kN=≤2.2; dynamic_force_kN=≤1.1; specimen_thickness_mm=≤2; specimen_diameter_mm=3–5; width_mm=≤10 | limited |
| [mts-advantage-optical-extensometer-aox](equipment/mts/mts-advantage-optical-extensometer-aox.json) | **센서** | extensometer | tensile, flexure, fatigue, creep, compression | – | – | data_rate_Hz=300–3000; displacement_um=≥0.1; gauge_length_mm=≥10 | limited |
| [mts-advantage-pneumatic-grips](equipment/mts/mts-advantage-pneumatic-grips.json) | **부속** | grip_fixture | tensile | – | -40–200 | force_N=10–10000; specimen_thickness_mm=≤20; pressure_MPa=≤0.6 | limited |
| [mts-advantage-screw-action-grips](equipment/mts/mts-advantage-screw-action-grips.json) | **부속** | grip_fixture | tensile, peel, tear, shear | – | -129–200 | force_N=100–10000; specimen_thickness_mm=≤25 | limited |
| [mts-advantage-wedge-action-grips](equipment/mts/mts-advantage-wedge-action-grips.json) | **부속** | grip_fixture | tensile, peel, tear | 10–300 | -130–315 |  | limited |
| [mts-ahx850-ltx850-long-travel-extensometers](equipment/mts/mts-ahx850-ltx850-long-travel-extensometers.json) | **센서** | extensometer | tensile | – | – | displacement_mm=≤850; gauge_length_mm=10–100; operating_temperature_degC=5–50 | limited |
| [mts-bionix-grips](equipment/mts/mts-bionix-grips.json) | **부속** | grip_fixture | tensile, fatigue | – | -130–250 | force_N=32–5000 | limited |
| [mts-bionix-stainless-steel-compression-platens](equipment/mts/mts-bionix-stainless-steel-compression-platens.json) | **부속** | grip_fixture | compression | ≤10 | -130–250 | specimen_diameter_mm=≤150 | limited |
| [mts-bionix-tabletop](equipment/mts/mts-bionix-tabletop.json) | 계열 | servohydraulic_fatigue | fatigue, tensile, compression, torsion, flexure | – | – | dynamic_force_kN=15, 25; torque_Nm=150, 250; stroke_mm=100, 150; rotation_deg=≤135; vertical_test_space_mm=30–1335; horizontal_test_space_mm=460 | catalog |
| [mts-composite-test-fixtures](equipment/mts/mts-composite-test-fixtures.json) | **부속** | grip_fixture | compression, shear, flexure, peel, fatigue | – | -152–318 | static_force_kN=2.2–250 | limited |
| [mts-criterion-series-40](equipment/mts/mts-criterion-series-40.json) | 계열 | universal_testing_machine | tensile, compression, flexure, shear, peel, tear | 0.001–1200 | – | crosshead_speed_mm_min=0.005–3000; vertical_test_space_mm=820–2000; horizontal_test_space_mm=100–1000; data_rate_Hz=≤5000 | catalog |
| [mts-dcpd-direct-current-potential-drop-solution](equipment/mts/mts-dcpd-direct-current-potential-drop-solution.json) | **센서** | accessory | fracture_toughness, fatigue | – | – | current_A=≤20; voltage_V=≤5; bandwidth_Hz=≤300; channels=2, 7 | limited |
| [mts-em-adapters-and-extension-kits](equipment/mts/mts-em-adapters-and-extension-kits.json) | **부속** | accessory | tensile, compression | – | -130–315 | force_N=200–150000; height_mm=100–825 | limited |
| [mts-exceed-3-point-bend-fixtures](equipment/mts/mts-exceed-3-point-bend-fixtures.json) | **부속** | grip_fixture | flexure | 10–30 | -70–350 | hdt_span_mm=≤400; width_mm=≤60 | limited |
| [mts-exceed-series-40](equipment/mts/mts-exceed-series-40.json) | 계열 | universal_testing_machine | tensile, compression, flexure, shear, peel | 0.005–600 | – | crosshead_speed_mm_min=0.001–508; vertical_test_space_mm=700–1450; horizontal_test_space_mm=100–750; data_rate_Hz=≤2500 | catalog |
| [mts-fax1352-fundamental-automatic-extensometer](equipment/mts/mts-fax1352-fundamental-automatic-extensometer.json) | **센서** | extensometer | tensile | – | – | displacement_mm=≤80; gauge_length_mm=10–200; specimen_thickness_mm=0.2–40; specimen_diameter_mm=0.2–40; operating_temperature_degC=5–40 | limited |
| [mts-fundamental-90-degree-peel-fixture](equipment/mts/mts-fundamental-90-degree-peel-fixture.json) | **부속** | grip_fixture | peel | – | – | force_N=≤450; width_mm=12.7–95.3 | limited |
| [mts-fundamental-and-exceed-screw-action-grips](equipment/mts/mts-fundamental-and-exceed-screw-action-grips.json) | **부속** | grip_fixture | tensile, peel, shear | 5–10 | -70–350 | specimen_thickness_mm=≤16 | limited |
| [mts-fundamental-bollard-grips](equipment/mts/mts-fundamental-bollard-grips.json) | **부속** | grip_fixture | tensile | – | -10–80 | force_N=200–10000; wire_diameter_mm=≤16 | limited |
| [mts-fundamental-coefficient-of-friction-grips](equipment/mts/mts-fundamental-coefficient-of-friction-grips.json) | **부속** | grip_fixture | friction_coefficient | ≤1 | – | specimen_thickness_mm=≤5 | limited |
| [mts-fundamental-compression-platens](equipment/mts/mts-fundamental-compression-platens.json) | **부속** | grip_fixture | compression | 0.5–300 | -50–150 | specimen_diameter_mm=≤150 | limited |
| [mts-fundamental-nut-and-bolt-grips](equipment/mts/mts-fundamental-nut-and-bolt-grips.json) | **부속** | grip_fixture | tensile | 100–600 | 0–50 |  | limited |
| [mts-fundamental-vise-and-scissors-grips](equipment/mts/mts-fundamental-vise-and-scissors-grips.json) | **부속** | grip_fixture | tensile | – | -130–250 | force_N=10–5000; specimen_thickness_mm=≤14; pressure_MPa=≤1 | limited |
| [mts-fundamental-wedge-and-hydraulic-grips](equipment/mts/mts-fundamental-wedge-and-hydraulic-grips.json) | **부속** | grip_fixture | tensile | 10–600 | 0–50 | pressure_MPa=≤20 | limited |
| [mts-geotextile-puncture-fixture](equipment/mts/mts-geotextile-puncture-fixture.json) | **부속** | grip_fixture | puncture | ≤5 | – |  | limited |
| [mts-high-temperature-extensometers-632-5x](equipment/mts/mts-high-temperature-extensometers-632-5x.json) | **센서** | extensometer | tensile, compression, fatigue, thermomechanical_fatigue, creep | – | ≤1200 | gauge_length_mm=10–25 | limited |
| [mts-landmark-servohydraulic](equipment/mts/mts-landmark-servohydraulic.json) | 계열 | servohydraulic_fatigue | fatigue, fracture_toughness, thermomechanical_fatigue, tensile, compression, flexure, relaxation | – | – | dynamic_force_kN=5–500; stroke_mm=100, 150, 250; frequency_Hz=≤200; vertical_test_space_mm=0–2129; horizontal_test_space_mm=460, 533, 635, 762 | catalog |
| [mts-landmark-servohydraulic-materialtwin](equipment/mts/mts-landmark-servohydraulic-materialtwin.json) | 계열 (보탬→mts-landmark-servohydraulic) | servohydraulic_fatigue | fatigue, fracture_toughness, thermomechanical_fatigue, tensile, compression, flexure, relaxation, creep | – | – |  | catalog |
| [mts-lx-laser-extensometer](equipment/mts/mts-lx-laser-extensometer.json) | **센서** | extensometer | tensile, flexure | – | – | displacement_mm=8–127; data_rate_Hz=≤100 | limited |
| [mts-model-609-alignment-fixtures](equipment/mts/mts-model-609-alignment-fixtures.json) | **부속** | accessory | fatigue, tensile | 25–500 | – |  | limited |
| [mts-model-640-fracture-mechanics-clevis-grips](equipment/mts/mts-model-640-fracture-mechanics-clevis-grips.json) | **부속** | grip_fixture | fracture_toughness, fatigue | – | -129–177 | static_force_kN=≤60; specimen_thickness_mm=12.7–25.4 | limited |
| [mts-model-642-bend-fixtures](equipment/mts/mts-model-642-bend-fixtures.json) | **부속** | grip_fixture | flexure, fracture_toughness, fatigue | – | -129–149 | dynamic_force_kN=0.9–10; hdt_span_mm=14–152 | limited |
| [mts-model-643-compression-platens](equipment/mts/mts-model-643-compression-platens.json) | **부속** | grip_fixture | compression, fatigue | – | -129–177 | specimen_diameter_mm=60–300; pressure_MPa=≤689 | limited |
| [mts-model-680-high-temperature-grips](equipment/mts/mts-model-680-high-temperature-grips.json) | **부속** | grip_fixture | fatigue, tensile, creep | – | ≤1500 |  | limited |
| [mts-model-685-hydraulic-grip-supplies](equipment/mts/mts-model-685-hydraulic-grip-supplies.json) | **부속** | accessory | tensile, fatigue | – | -40–177 | pressure_MPa=0.7–70 | limited |
| [mts-multi-sample-fatigue-fixture-msf15](equipment/mts/mts-multi-sample-fatigue-fixture-msf15.json) | **부속** | grip_fixture | fatigue | – | 35–39 | stations=15; force_N=≤45 | limited |
| [mts-series-635-extensometers](equipment/mts/mts-series-635-extensometers.json) | **센서** | extensometer | tensile | – | -85–120 | gauge_length_mm=25–50 | limited |
| [mts-series-645-fatigue-rated-pneumatic-wedge-grips](equipment/mts/mts-series-645-fatigue-rated-pneumatic-wedge-grips.json) | **부속** | grip_fixture | fatigue, tensile | – | -40–200 | dynamic_force_kN=2–12; pressure_MPa=≤1.03; specimen_thickness_mm=≤12.4 | limited |
| [mts-series-646-hydraulic-collet-grips](equipment/mts/mts-series-646-hydraulic-collet-grips.json) | **부속** | grip_fixture | fatigue, tensile, torsion | 100–250 | -40–1000 | torque_Nm=≤2200; specimen_diameter_mm=10–30 | limited |
| [mts-series-647-hydraulic-wedge-grips](equipment/mts/mts-series-647-hydraulic-wedge-grips.json) | **부속** | grip_fixture | tensile, fatigue, shear, fracture_toughness, peel, torsion | – | -130–540 | dynamic_force_kN=≥25; static_force_kN=≥31 | limited |

## NAPSON Corporation (`napson`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [napson-cresbox](equipment/napson/napson-cresbox.json) | 기종 | electrical_property_tester | electrical_transport | – | – | surface_resistivity_ohm_sq=0.005–10000000.0; resistivity_ohm_cm=0.001–300000.0; wafer_size_mm=≤200; sample_size_mm=≤156 | limited |
| [napson-eddy-current-ec-80-nc-80map](equipment/napson/napson-eddy-current-ec-80-nc-80map.json) | 계열 | electrical_property_tester | electrical_transport | – | – | surface_resistivity_ohm_sq=0.01–3000; resistivity_ohm_cm=0.001–200; wafer_size_mm=≤300 | limited |
| [napson-rg-200pv](equipment/napson/napson-rg-200pv.json) | 기종 | electrical_property_tester | electrical_transport | – | – | surface_resistivity_ohm_sq=0.001–1000000.0; resistivity_ohm_cm=0.001–10000.0; sample_size_mm=≤210 | limited |
| [napson-rt-3000-systems](equipment/napson/napson-rt-3000-systems.json) | 계열 | electrical_property_tester | electrical_transport | – | – | surface_resistivity_ohm_sq=0.001–1000000000.0; resistivity_ohm_cm=0.0001–1000000.0; wafer_size_mm=≤300; sample_size_mm=≤1850 | limited |
| [napson-rt-70v](equipment/napson/napson-rt-70v.json) | 계열 | electrical_property_tester | electrical_transport | – | – | surface_resistivity_ohm_sq=0.005–10000000.0; resistivity_ohm_cm=1e-06–300000.0; wafer_size_mm=≤300; sample_size_mm=≤920 | limited |
| [napson-tcr-600](equipment/napson/napson-tcr-600.json) | 기종 | electrical_property_tester | electrical_transport | – | ≤600 | resistivity_ohm_cm=1e-05–100000.0; sample_size_mm=5–35 | limited |

## NETZSCH Analyzing & Testing (`netzsch`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [netzsch-arc-244-305](equipment/netzsch/netzsch-arc-244-305.json) | 계열 | accelerating_rate_calorimeter | thermal_runaway_calorimetry, battery_abuse | – | 20–500 | pressure_bar=0–150; sample_volume_mL=0.5–130; tracking_rate_K_min=≤200; temperature_reproducibility_K=≤0.1 | catalog |
| [netzsch-dil-402-expedis](equipment/netzsch/netzsch-dil-402-expedis.json) | 계열 | dilatometer | dilatometry, tma | – | -180–2800 | heating_rate_K_min=0.001–100; displacement_um=≤25000; force_N=0.01–3; sample_length_mm=≤52; specimen_diameter_mm=≤19 | catalog |
| [netzsch-dil-402-expedis-materialtwin](equipment/netzsch/netzsch-dil-402-expedis-materialtwin.json) | 계열 (보탬→netzsch-dil-402-expedis) | dilatometer | dilatometry, tma | – | – |  | catalog |
| [netzsch-dma-242-e-artemis](equipment/netzsch/netzsch-dma-242-e-artemis.json) | 계열 | dma | dma | – | -170–600 | heating_rate_K_min=0.01–20; frequency_Hz=0.01–100; force_N=≤24 | catalog |
| [netzsch-dsc-214-polyma](equipment/netzsch/netzsch-dsc-214-polyma.json) | 계열 | dsc | dsc | – | -170–600 | heating_rate_K_min=0.001–500 | catalog |
| [netzsch-dsc-300-caliris](equipment/netzsch/netzsch-dsc-300-caliris.json) | 계열 | dsc | dsc | – | -180–750 | heating_rate_K_min=≤500; sample_mass_mg=– | catalog |
| [netzsch-hfm-446-lambda](equipment/netzsch/netzsch-hfm-446-lambda.json) | 계열 | thermal_conductivity | thermal_conductivity | – | -30–90 | thermal_conductivity_W_mK=0.001–2 | catalog |
| [netzsch-lfa-400](equipment/netzsch/netzsch-lfa-400.json) | 계열 | thermal_conductivity | thermal_conductivity | – | -125.0–2800.0 |  | catalog |
| [netzsch-lfa-467-hyperflash](equipment/netzsch/netzsch-lfa-467-hyperflash.json) | 계열 | thermal_conductivity | thermal_conductivity | – | -100–1250 | heating_rate_K_min=≤50; thermal_diffusivity_mm2_s=0.01–2000; thermal_conductivity_W_mK=0.1–4000; specimen_diameter_mm=≤25.4; specimen_thickness_mm=0.01–6; stati | catalog |
| [netzsch-sta-2500-regulus](equipment/netzsch/netzsch-sta-2500-regulus.json) | 계열 | sta | tga, dsc | – | 20–1600 | heating_rate_K_min=0.001–100 | catalog |
| [netzsch-sta-449](equipment/netzsch/netzsch-sta-449.json) | 계열 | sta | tga, dsc | – | -150.0–2400.0 |  | catalog |
| [netzsch-tg-209-f1-libra](equipment/netzsch/netzsch-tg-209-f1-libra.json) | 계열 | tga | tga | – | ≤1100 |  | limited |
| [netzsch-tg-209-f3-tarsus](equipment/netzsch/netzsch-tg-209-f3-tarsus.json) | 기종 | tga | tga | – | 20–1000 | heating_rate_K_min=0.001–200; sample_mass_mg=≤2000; balance_resolution_ug=0.1 | catalog |
| [netzsch-tma-402-hyperion](equipment/netzsch/netzsch-tma-402-hyperion.json) | 계열 | tma | tma, dma, creep, relaxation | – | -150–1550 | heating_rate_K_min=0.001–50; force_N=0.001–4; displacement_um=≤2500; frequency_Hz=0.0003–1; sample_length_mm=≤30 | catalog |

## Neware Technology (`neware`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [neware-bts4000](equipment/neware/neware-bts4000.json) | 기종 | battery_cycler | battery_cycle_life | – | – | voltage_V=0.025–5; current_A=0.0005–6; channel_power_W=≤30; channels=8; step_duration_h=≤8760; data_interval_ms=≥100 | catalog |

## Newtons4th (N4L) (`newtons4th`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [newtons4th-ppa-series](equipment/newtons4th/newtons4th-ppa-series.json) | 계열 | power_analyzer | power_consumption | – | – | current_A=≤300; energy_resolution_mWh=≤0.1; integration_time_resolution_s=≤1 | limited |

## NI (National Instruments) (`ni`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [ni-compactdaq-chassis](equipment/ni/ni-compactdaq-chassis.json) | 계열 | dmm_daq |  | – | – |  | limited |

## Nikon Metrology (`nikon`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [nikon-eclipse-lv-n-series](equipment/nikon/nikon-eclipse-lv-n-series.json) | 계열 | optical_microscope | microscopy | – | – | specimen_height_mm=≤73; stage_travel_mm=≤150 | limited |
| [nikon-smz25-smz18](equipment/nikon/nikon-smz25-smz18.json) | 계열 | optical_microscope | microscopy | – | – | zoom_ratio=25, 18; magnification=3.15–315; working_distance_mm=20–71; field_of_view_mm=≤70; optical_resolution_lp_mm=≤1100 | catalog |
| [nikon-xt-h-series](equipment/nikon/nikon-xt-h-series.json) | 계열 | xray_inspection | xray_void_inspection | – | – | tube_voltage_kV=180–225; spot_size_um=≥3 | catalog |

## Nittoseiko Analytech Co., Ltd. (`nittoseiko-analytech`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [nittoseiko-analytech-hiresta-ux](equipment/nittoseiko-analytech/nittoseiko-analytech-hiresta-ux.json) | 기종 | electrical_property_tester | electrical_transport | – | – | resistance_ohm=1000–100000000000000.0; voltage_V=1–1000 | limited |
| [nittoseiko-analytech-loresta](equipment/nittoseiko-analytech/nittoseiko-analytech-loresta.json) | 계열 | electrical_property_tester | electrical_transport | – | – | resistance_ohm=0.0001–10000000.0; current_A=1e-07–1; probe_spacing_mm=1.0, 1.5, 2.5, 5, 10; sample_size_mm=≤300 | limited |

## Noise Laboratory (NOISEKEN) (`noiseken`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [noiseken-ess-esd-simulators](equipment/noiseken/noiseken-ess-esd-simulators.json) | 계열 | esd_simulator | esd_immunity | – | – | esd_voltage_kV=0.2–30.0; discharge_mode=contact, air; polarity=positive, negative | limited |
| [noiseken-ess-s3011a](equipment/noiseken/noiseken-ess-s3011a.json) | 기종 | esd_simulator | esd_immunity | – | – | esd_voltage_kV=0.2–30.0; discharge_mode=contact, air; polarity=positive, negative | catalog |

## Nordson Test & Inspection (DAGE / Sonoscan) (`nordson-dage`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [nordson-dage-4000plus-bondtester](equipment/nordson-dage/nordson-dage-4000plus-bondtester.json) | 기종 | bond_tester | wire_bond_strength | – | – | push_force_kgf=≤50; pull_force_kgf=≤100; shear_force_kgf=≤200; stage_travel_mm=≤300 | catalog |
| [nordson-dage-quadra-xray](equipment/nordson-dage/nordson-dage-quadra-xray.json) | 계열 | xray_inspection | xray_void_inspection | – | – | tube_voltage_kV=30–160; tube_power_W=10–20; feature_recognition_um=≥0.1; magnification=≤68000; inspection_area_mm=≤510; sample_size_mm=≤740; sample_weight_kg=≤5 | catalog |
| [nordson-dage-sonoscan-gen6](equipment/nordson-dage/nordson-dage-sonoscan-gen6.json) | 기종 | acoustic_microscope | acoustic_delamination | – | – | wafer_size_mm=≤300; transducer_frequency_MHz=– | limited |
| [nordson-gen7-c-sam](equipment/nordson-dage/nordson-gen7-c-sam.json) | 기종 | acoustic_microscope | acoustic_delamination | – | – |  | limited |

## Norman Tool, Inc. (`norman-tool`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [norman-tool-rca-abrader](equipment/norman-tool/norman-tool-rca-abrader.json) | 계열 | abrasion_tester | abrasion | – | – | load_g=55, 175, 275; cycle_rate_cpm=20 | limited |

## OMRON (`omron`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [omron-zw](equipment/omron/omron-zw.json) | 계열 | thickness_displacement_gauge |  | – | – | measurement_distance_mm=7–40; displacement_mm=-3–3; spot_size_um=4–190; position_resolution_nm=250; linearity_um=0.3; sampling_cycle_us=20–7500 | catalog |

## Optris GmbH (`optris`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [optris-pi-series](equipment/optris/optris-pi-series.json) | 계열 | thermal_imager | thermography | – | -20–3000 | ir_resolution_pixels=110016–366720; thermal_sensitivity_degC=0.04–0.06; frame_rate_fps=32–80; max_frame_rate_fps=≤1000 | limited |

## Optronis GmbH (`optronis`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [optronis-cyclone-series](equipment/optronis/optronis-cyclone-series.json) | 계열 | high_speed_swir_camera |  | – | – | resolution_pixels=≤65408000; frame_rate_fps=71–3518 | limited |

## Ossila (`ossila`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [ossila-four-point-probe](equipment/ossila/ossila-four-point-probe.json) | 기종 | electrical_property_tester | electrical_transport | – | – |  | catalog |

## Oxford Instruments (`oxford-instruments`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [oxford-symmetry-s2](equipment/oxford-instruments/oxford-symmetry-s2.json) | 기종 | electron_microscope | crystal_structure_analysis | – | – |  | catalog |

## Panasonic Industry (`panasonic`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [panasonic-hg-c](equipment/panasonic/panasonic-hg-c.json) | 계열 | thickness_displacement_gauge |  | – | – | measurement_distance_mm=30–400; displacement_mm=-200–200; measuring_repeatability_um=10–800; spot_size_um=50–500 | limited |

## Park Systems (`park-systems`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [park-nx10](equipment/park-systems/park-nx10.json) | 기종 | atomic_force_microscope | surface_topography | – | – |  | limited |

## PerkinElmer (`perkinelmer`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [perkinelmer-dma-8000](equipment/perkinelmer/perkinelmer-dma-8000.json) | 기종 | dma | dma, compression | – | -190.0–600.0 |  | catalog |
| [perkinelmer-dsc-8000](equipment/perkinelmer/perkinelmer-dsc-8000.json) | 계열 | dsc | dsc | – | – | heating_rate_K_min=0.01–750; pressure_psi=≤600 | limited |
| [perkinelmer-frontier-ftir](equipment/perkinelmer/perkinelmer-frontier-ftir.json) | 기종 | composition_spectrometer | composition_analysis | – | – |  | limited |
| [perkinelmer-pyris-dsc-9](equipment/perkinelmer/perkinelmer-pyris-dsc-9.json) | 계열 | dsc | dsc | – | -100–750 | heating_rate_K_min=0.1–100 | catalog |
| [perkinelmer-pyris-sta-9](equipment/perkinelmer/perkinelmer-pyris-sta-9.json) | 계열 | sta | tga, dsc | – | 15–1100 | heating_rate_K_min=1–300 | catalog |
| [perkinelmer-pyris-tga-9](equipment/perkinelmer/perkinelmer-pyris-tga-9.json) | 계열 | tga | tga | – | 15–1100 | heating_rate_K_min=1–300 | catalog |

## Photo Research (Novanta / JADAK) (`photo-research`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [photo-research-spectrascan-benchtop](equipment/photo-research/photo-research-spectrascan-benchtop.json) | 계열 | spectroradiometer | photometry_colorimetry | – | – | wavelength_nm=380–780; measuring_angle_deg=2, 1, 0.5, 0.25, 0.125, 0.2, 0.1; measurement_time_s=0.3–75 | limited |
| [photo-research-spectrascan-portable](equipment/photo-research/photo-research-spectrascan-portable.json) | 계열 | spectroradiometer | photometry_colorimetry | – | – | wavelength_nm=380–780; luminance_cd_m2=0.6852–8565000; measuring_angle_deg=1, 0.5, 0.25, 0.125 | limited |

## Photron (`photron`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [photron-fastcam-mini-ax](equipment/photron/photron-fastcam-mini-ax.json) | 계열 | high_speed_swir_camera |  | – | – | resolution_pixels=≤1048576; frame_rate_fps=2000–6400; max_frame_rate_fps=≤900000; min_exposure_time_s=≥1e-06; memory_GB=8, 16, 32; adc_resolution_bit=12 | catalog |
| [photron-fastcam-mini-ux](equipment/photron/photron-fastcam-mini-ux.json) | 계열 | high_speed_swir_camera |  | – | – | resolution_pixels=≤1310720; frame_rate_fps=2000–4000; max_frame_rate_fps=≤800000; pixel_pitch_um=10; min_exposure_time_s=≥1.01e-06 | catalog |
| [photron-fastcam-mini-wx](equipment/photron/photron-fastcam-mini-wx.json) | 계열 | high_speed_swir_camera |  | – | – | resolution_pixels=≤4194304; frame_rate_fps=750–1080; max_frame_rate_fps=≤80000; min_exposure_time_s=≥2.7e-06 | catalog |
| [photron-fastcam-nova-s](equipment/photron/photron-fastcam-nova-s.json) | 계열 | high_speed_swir_camera |  | – | – | resolution_pixels=≤1048576; frame_rate_fps=6400–16000; max_frame_rate_fps=≤1100000; min_exposure_time_s=≥2e-07; memory_GB=16, 32, 64, 128 | catalog |
| [photron-fastcam-sa-series](equipment/photron/photron-fastcam-sa-series.json) | 계열 | high_speed_swir_camera |  | – | – | frame_rate_fps=3600–20000; max_frame_rate_fps=≤2100000 | limited |

## Proceq (Screening Eagle) (`proceq`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [proceq-equotip-550-leeb](equipment/proceq/proceq-equotip-550-leeb.json) | 기종 | portable_hardness | hardness_leeb | – | – | hardness_scales=HLD, HLDC, HLDL, HLS, HLE, HLG, HLC; impact_energy_Nmm=3, 11, 90; sample_mass_kg=≥0.02 | catalog |

## PVA TePla Analytical Systems (`pva-tepla`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [pva-tepla-sam](equipment/pva-tepla/pva-tepla-sam.json) | 계열 | acoustic_microscope | acoustic_delamination | – | – | transducer_frequency_MHz=≤400; sample_size_mm=≤670; wafer_size_mm=200, 300 | limited |

## Q-Lab Corporation (`q-lab`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [q-lab-q-fog](equipment/q-lab/q-lab-q-fog.json) | 계열 | corrosion_chamber | salt_spray_corrosion, damp_heat | – | – | chamber_volume_L=600, 1100; humidity_pct=20–100 | catalog |
| [q-lab-q-sun](equipment/q-lab/q-lab-q-sun.json) | 계열 | weathering_tester | accelerated_weathering | – | – | irradiance_control_nm=340, 420, 300-400 (TUV); humidity_pct=–; stations=17, 31, 55 | catalog |
| [q-lab-quv](equipment/q-lab/q-lab-quv.json) | 기종 | weathering_tester | accelerated_weathering | – | – |  | limited |

## Radiant Vision Systems (`radiant-vision-systems`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [radiant-vision-systems-prometric-i](equipment/radiant-vision-systems/radiant-vision-systems-prometric-i.json) | 계열 | imaging_colorimeter | photometry_colorimetry | – | – | resolution_pixels=1920000–61043840; luminance_cd_m2=1e-05–1010; dynamic_range_dB=59–76; measurement_time_s=0.3–2.4 | catalog |
| [radiant-vision-systems-prometric-y](equipment/radiant-vision-systems/radiant-vision-systems-prometric-y.json) | 계열 | imaging_colorimeter | photometry_colorimetry | – | – | resolution_pixels=16105984–61043840; luminance_cd_m2=0.0001–1010; dynamic_range_dB=66–76 | catalog |

## Renishaw (`renishaw`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [renishaw-invia](equipment/renishaw/renishaw-invia.json) | 계열 | composition_spectrometer | composition_analysis | – | – |  | limited |

## RHESCA Co., Ltd. (`rhesca`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [rhesca-friction-testers](equipment/rhesca/rhesca-friction-testers.json) | 계열 | tribometer | friction_wear_tribo | – | ≤200 (부속) | force_N=0.49–2000; friction_force_mN=2.45–2000000; rotation_rpm=0.1–600; sliding_speed_m_s=1e-05–3.141; frequency_Hz=≤50; humidity_pct=20–80 | limited |
| [rhesca-ptr1102](equipment/rhesca/rhesca-ptr1102.json) | 기종 | bond_tester | wire_bond_strength | – | – | pull_force_kgf=≤20; push_force_kgf=≤20; shear_force_kgf=≤100; measuring_speed_mm_s=0.001–10; stage_travel_mm=≤100 | limited |
| [rhesca-scratch-testers](equipment/rhesca/rhesca-scratch-testers.json) | 계열 | scratch_hardness_tester | scratch_pencil_hardness | – | – | load_N=0.001–294.2; scratch_speed_mm_min=≤60; stylus_radius_um=5–500 | limited |
| [rhesca-solder-wettability-testers](equipment/rhesca/rhesca-solder-wettability-testers.json) | 계열 | solderability_tester | solderability | – | ≤900 | wetting_force_mN=≤50; dip_depth_mm=0.005–28; dip_speed_mm_s=0.1–30 | limited |

## Rigaku (`rigaku`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [rigaku-smartlab](equipment/rigaku/rigaku-smartlab.json) | 기종 | xray_diffractometer | crystal_structure_analysis, dsc, coating_thickness | – | – |  | catalog |
| [rigaku-stavesta](equipment/rigaku/rigaku-stavesta.json) | 계열 | sta | tga, dsc | – | -40–1500 | heating_rate_K_min=≤100 | catalog |
| [rigaku-thermo-plus-dsc](equipment/rigaku/rigaku-thermo-plus-dsc.json) | 계열 | dsc | dsc | – | -180–1500 (부속) | heating_rate_K_min=≤150; heat_flow_mW=≤1000; heat_flow_noise_uW_rms=0.05–5 | catalog |
| [rigaku-tma8311](equipment/rigaku/rigaku-tma8311.json) | 계열 | tma | tma | – | -150–1500 (부속) | force_N=≤1; heating_rate_K_min=≤100; displacement_um=-5000–5000; frequency_Hz=0.01–1 | catalog |
| [rigaku-zsx-primus-400](equipment/rigaku/rigaku-zsx-primus-400.json) | 기종 | composition_spectrometer | composition_analysis | – | – |  | catalog |

## RIGOL Technologies (`rigol`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [rigol-dg1000z](equipment/rigol/rigol-dg1000z.json) | 계열 | signal_generator |  | – | – | output_frequency_Hz=≤60000000; channels=2; sample_rate_Sa_s=200000000; dac_resolution_bit=14; waveform_memory_pts=2000000, 8000000, 16000000; phase_noise_dBc_Hz | limited |
| [rigol-dg2000](equipment/rigol/rigol-dg2000.json) | 계열 | signal_generator |  | – | – | output_frequency_Hz=≤100000000; channels=2; dac_resolution_bit=16; waveform_memory_pts=16000000; sample_rate_Sa_s=≤250000000; output_voltage_V=0.001–10; phase_n | catalog |
| [rigol-dg800](equipment/rigol/rigol-dg800.json) | 계열 | signal_generator |  | – | – | output_frequency_Hz=≤35000000; channels=1, 2; dac_resolution_bit=16; waveform_memory_pts=2000000, 8000000 | limited |
| [rigol-dg800-pro](equipment/rigol/rigol-dg800-pro.json) | 계열 | signal_generator |  | – | – | output_frequency_Hz=≤50000000; channels=1, 2; sample_rate_Sa_s=625000000; dac_resolution_bit=16; waveform_memory_pts=2000000, 8000000; weight_kg=1.78 | limited |
| [rigol-dg900](equipment/rigol/rigol-dg900.json) | 계열 | signal_generator |  | – | – | output_frequency_Hz=≤100000000; channels=2; dac_resolution_bit=16; waveform_memory_pts=16000000 | limited |
| [rigol-dg900-pro](equipment/rigol/rigol-dg900-pro.json) | 계열 | signal_generator |  | – | – | output_frequency_Hz=≤200000000; channels=2; sample_rate_Sa_s=1250000000; dac_resolution_bit=16; waveform_memory_pts=16000000, 32000000 | limited |
| [rigol-dho-mho5000](equipment/rigol/rigol-dho-mho5000.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=500000000–1000000000; sample_rate_Sa_s=≤4000000000; record_length_pts=≤500000000; channels=4, 6, 8; logic_channel_count=16 | limited |
| [rigol-dho1000](equipment/rigol/rigol-dho1000.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=70000000–200000000; sample_rate_Sa_s=≤2000000000; record_length_pts=≤50000000; channels=2, 4; adc_resolution_bit=12 | limited |
| [rigol-dho4000](equipment/rigol/rigol-dho4000.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=200000000–800000000; sample_rate_Sa_s=≤4000000000; record_length_pts=≤250000000; channels=4; adc_resolution_bit=12 | limited |
| [rigol-dho800](equipment/rigol/rigol-dho800.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=70000000–100000000; sample_rate_Sa_s=≤1250000000; record_length_pts=≤25000000; channels=2, 4; adc_resolution_bit=12; display_size_in=7 | limited |
| [rigol-dho900](equipment/rigol/rigol-dho900.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=125000000–250000000; sample_rate_Sa_s=≤1250000000; record_length_pts=≤50000000; channels=4; logic_channel_count=16; adc_resolution_bit=12 | limited |
| [rigol-ds1000z](equipment/rigol/rigol-ds1000z.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=50000000–200000000; channels=2, 4; logic_channel_count=16; record_length_pts=≤12000000 | limited |
| [rigol-mso5000](equipment/rigol/rigol-mso5000.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=70000000–350000000; sample_rate_Sa_s=≤8000000000; record_length_pts=≤100000000; channels=2, 4; logic_channel_count=16 | limited |
| [rigol-mso8000](equipment/rigol/rigol-mso8000.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=600000000–2000000000; sample_rate_Sa_s=≤10000000000; record_length_pts=≤500000000; channels=4; logic_channel_count=16 | limited |

## RION Co., Ltd. (`rion`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [rion-na-28](equipment/rion/rion-na-28.json) | 기종 | acoustic_measurement |  | – | – |  | limited |
| [rion-nl-sound-level-meters](equipment/rion/rion-nl-sound-level-meters.json) | 계열 | acoustic_measurement |  | – | – | frequency_Hz=≥1; accuracy_class=Class 1, Class 2 | limited |

## Rohde & Schwarz (`rohde-schwarz`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [rohde-schwarz-cmp180](equipment/rohde-schwarz/rohde-schwarz-cmp180.json) | 계열 | radio_communication_tester |  | – | – | frequency_Hz=≤8000000000; bandwidth_Hz=≤500000000; channels=≤2; rf_port_count=≤16; radio_standards=Wi-Fi 6E (802.11ax), Wi-Fi 7 (802.11be), Wi-Fi 8 (802.11bn),  | catalog |
| [rohde-schwarz-cmp200](equipment/rohde-schwarz/rohde-schwarz-cmp200.json) | 계열 | radio_communication_tester |  | – | – | frequency_Hz=6000000000–20000000000; radio_standards=5G FR2 (CMPHEAD30 원격 헤드 사용) | catalog |
| [rohde-schwarz-cmu200](equipment/rohde-schwarz/rohde-schwarz-cmu200.json) | 계열 | radio_communication_tester |  | – | – | radio_standards=GSM/GPRS/EDGE, TDMA (IS-136), AMPS, CDMA2000 1xRTT, CDMA2000 1xEV-DO, WCDMA/HSPA, Bluetooth | limited |
| [rohde-schwarz-cmw100](equipment/rohde-schwarz/rohde-schwarz-cmw100.json) | 계열 | radio_communication_tester |  | – | – | frequency_Hz=≤6000000000; bandwidth_Hz=≤160000000; rf_port_count=≤8; radio_standards=LTE, 5G NR, WLAN, Bluetooth, IoT | limited |
| [rohde-schwarz-cmw270](equipment/rohde-schwarz/rohde-schwarz-cmw270.json) | 계열 | radio_communication_tester |  | – | – | bandwidth_Hz=≤160000000; radio_standards=Bluetooth LE, Bluetooth BR, Bluetooth EDR, WLAN 802.11a/b/g/n/ac/ax, GNSS(ARB), 방송(ARB) | catalog |
| [rohde-schwarz-cmw290](equipment/rohde-schwarz/rohde-schwarz-cmw290.json) | 계열 | radio_communication_tester |  | – | – | radio_standards=NB-IoT (R13-15, Cat. NB1/2), LTE-M (R13-14, Cat.1/0/M1/M2), GSM, WCDMA, LTE, WLAN 802.11a/b/g/n/ac/ax, Bluetooth | limited |
| [rohde-schwarz-cmw500](equipment/rohde-schwarz/rohde-schwarz-cmw500.json) | 계열 | radio_communication_tester |  | – | – | radio_standards=LTE, LTE-Advanced, NB-IoT, NB-NTN, WCDMA, GSM, WLAN 802.11a/b/g/n/ac/ax, Bluetooth Classic; frequency_Hz=≤6000000000 | catalog |
| [rohde-schwarz-cmx500](equipment/rohde-schwarz/rohde-schwarz-cmx500.json) | 계열 | radio_communication_tester |  | – | – | frequency_Hz=≤50000000000; radio_standards=5G NR (SA/NSA), LTE, WLAN IEEE 802.11bn (Wi-Fi 8), NR-NTN, NB-NTN, Direct-To-Cell (D2C/DTC); bandwidth_Hz=≤1000000000 | catalog |
| [rohde-schwarz-mxo-3](equipment/rohde-schwarz/rohde-schwarz-mxo-3.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=100000000–1000000000; channels=4, 8; sample_rate_Sa_s=≤5000000000; record_length_pts=125000000–500000000; adc_resolution_bit=12; logic_channel_coun | limited |
| [rohde-schwarz-mxo-4](equipment/rohde-schwarz/rohde-schwarz-mxo-4.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=200000000–1500000000; sample_rate_Sa_s=≤5000000000; record_length_pts=400000000–800000000; channels=4; logic_channel_count=16; display_size_in=13.3 | limited |
| [rohde-schwarz-mxo-5](equipment/rohde-schwarz/rohde-schwarz-mxo-5.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=100000000–2000000000; channels=4, 8; adc_resolution_bit=12; display_size_in=15.6; sample_rate_Sa_s=≤5000000000; record_length_pts=500000000–1000000 | limited |
| [rohde-schwarz-rta4000](equipment/rohde-schwarz/rohde-schwarz-rta4000.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=200000000–1000000000; sample_rate_Sa_s=≤5000000000; record_length_pts=≤200000000; channels=4; logic_channel_count=16; adc_resolution_bit=10; displa | limited |
| [rohde-schwarz-rtb-2](equipment/rohde-schwarz/rohde-schwarz-rtb-2.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=70000000–300000000; sample_rate_Sa_s=≤2500000000; record_length_pts=10000000–20000000; channels=2, 4; logic_channel_count=16; adc_resolution_bit=10 | limited |
| [rohde-schwarz-rtb2000](equipment/rohde-schwarz/rohde-schwarz-rtb2000.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=70000000–300000000; channels=2, 4; logic_channel_count=16; sample_rate_Sa_s=≤2500000000; record_length_pts=10000000–20000000; adc_resolution_bit=10 | catalog |
| [rohde-schwarz-rtm3000](equipment/rohde-schwarz/rohde-schwarz-rtm3000.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=100000000–1000000000; sample_rate_Sa_s=≤5000000000; record_length_pts=40000000–80000000; channels=2, 4; logic_channel_count=16; adc_resolution_bit= | limited |
| [rohde-schwarz-rto6](equipment/rohde-schwarz/rohde-schwarz-rto6.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=600000000–6000000000; sample_rate_Sa_s=≤20000000000; record_length_pts=200000000–2000000000; channels=4; logic_channel_count=16; display_size_in=15 | limited |
| [rohde-schwarz-rtp](equipment/rohde-schwarz/rohde-schwarz-rtp.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=4000000000–16000000000; sample_rate_Sa_s=20000000000–40000000000; channels=4; logic_channel_count=16; record_length_pts=100000000–3000000000 | limited |
| [rohde-schwarz-sma100b](equipment/rohde-schwarz/rohde-schwarz-sma100b.json) | 계열 | signal_generator |  | – | – | output_frequency_Hz=8000–67000000000; rf_output_level_dBm=-127–30; phase_noise_dBc_Hz=-140, -120, -132 | catalog |
| [rohde-schwarz-smb100b](equipment/rohde-schwarz/rohde-schwarz-smb100b.json) | 계열 | signal_generator |  | – | – | output_frequency_Hz=8000–40000000000; rf_output_level_dBm=-127–26; phase_noise_dBc_Hz=-126, -112 | catalog |
| [rohde-schwarz-smbv100b](equipment/rohde-schwarz/rohde-schwarz-smbv100b.json) | 계열 | signal_generator |  | – | – | output_frequency_Hz=8000–6000000000; bandwidth_Hz=≤1000000000; rf_output_level_dBm=-127–25; phase_noise_dBc_Hz=-134; waveform_memory_pts=64000000, 512000000, 10 | catalog |
| [rohde-schwarz-smcv100b](equipment/rohde-schwarz/rohde-schwarz-smcv100b.json) | 계열 | signal_generator |  | – | – | output_frequency_Hz=4000–7125000000; bandwidth_Hz=≤240000000; rf_output_level_dBm=-120–20; radio_standards=5G NR, LTE, GSM/EDGE, Bluetooth, WLAN 802.11a/b/g/n/a | catalog |
| [rohde-schwarz-smm100a](equipment/rohde-schwarz/rohde-schwarz-smm100a.json) | 계열 | signal_generator |  | – | – | output_frequency_Hz=100000–44000000000; bandwidth_Hz=120000000–2000000000; rf_output_level_dBm=-120–18; phase_noise_dBc_Hz=-129; radio_standards=5G NR, Wi-Fi 8, | catalog |
| [rohde-schwarz-smw200a](equipment/rohde-schwarz/rohde-schwarz-smw200a.json) | 계열 | signal_generator |  | – | – | output_frequency_Hz=100000–67000000000; bandwidth_Hz=≤2000000000; rf_output_level_dBm=-120–18; channels=≤2; radio_standards=5G NR, WLAN IEEE 802.11be, GNSS, 레이더 | catalog |
| [rs-esw-emi-receiver](equipment/rohde-schwarz/rs-esw-emi-receiver.json) | 계열 | emi_receiver | emi_emission | – | – | frequency_Hz=2–44000000000; resolution_bandwidth_Hz=≤1000000 | catalog |
| [rs-zna-vna](equipment/rohde-schwarz/rs-zna-vna.json) | 계열 | network_lcr_analyzer |  | – | – | frequency_Hz=10000000–110000000000; rf_port_count=2, 4; rf_output_level_dBm=≤17 | limited |
| [rs-znb3000-vna](equipment/rohde-schwarz/rs-znb3000-vna.json) | 계열 | network_lcr_analyzer |  | – | – | frequency_Hz=9000–54000000000; rf_port_count=2, 4; dynamic_range_dB=≤150; rf_output_level_dBm=≤18 | limited |
| [rs-znl-vna](equipment/rohde-schwarz/rs-znl-vna.json) | 계열 | network_lcr_analyzer |  | – | – | frequency_Hz=5000–20000000000; rf_port_count=2; rf_output_level_dBm=≤0; weight_kg=6–8 | limited |
| [rs-znle-vna](equipment/rohde-schwarz/rs-znle-vna.json) | 계열 | network_lcr_analyzer |  | – | – | frequency_Hz=100000–20000000000; rf_port_count=2; rf_output_level_dBm=≤0 | limited |

## Royce Instruments (`royce-instruments`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [royce-instruments-bond-testers](equipment/royce-instruments/royce-instruments-bond-testers.json) | 계열 | bond_tester | wire_bond_strength | – | – | wafer_size_mm=≤300; data_rate_Hz=≤100000 | limited |

## Rtec Instruments (`rtec-instruments`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [rtec-instruments-fbt-1000](equipment/rtec-instruments/rtec-instruments-fbt-1000.json) | 기종 | tribometer | friction_wear_tribo | – | -35–200 | force_N=≤10000; rotation_rpm=≤2500 | limited |
| [rtec-instruments-mft](equipment/rtec-instruments/rtec-instruments-mft.json) | 계열 | tribometer | friction_wear_tribo | – | -120–1200 (부속) | force_N=0.001–10000; rotation_rpm=0.001–30000; frequency_Hz=0.01–500; stroke_mm=0.005–60; sliding_speed_m_s=≤0.37; humidity_pct=5–95 | limited |

## Saginomiya Seisakusho, Inc. (`saginomiya`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [saginomiya-bmh-lst](equipment/saginomiya/saginomiya-bmh-lst.json) | 계열 | servohydraulic_fatigue | fatigue, tensile, compression | – | – | dynamic_force_kN=300–2000 | limited |
| [saginomiya-smh-material-fatigue](equipment/saginomiya/saginomiya-smh-material-fatigue.json) | 계열 | servohydraulic_fatigue | fatigue, tensile, compression | – | – | dynamic_force_kN=20–300; static_force_kN=23–350 | limited |

## SALT Co. (Light-SALT) (`salt`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [salt-st-1000-series-electromechanical-utm](equipment/salt/salt-st-1000-series-electromechanical-utm.json) | 계열 | universal_testing_machine | tensile, compression, flexure, peel, tear | 3–300 | -100–1200 (부속) | crosshead_speed_mm_min=0.01–2000; vertical_test_space_mm=600–1290; horizontal_test_space_mm=170–620; weight_kg=70–1450 | limited |
| [salt-st-1004-hydraulic-utm](equipment/salt/salt-st-1004-hydraulic-utm.json) | 계열 | hydraulic_utm | tensile, compression, flexure | 300–3000 | – | crosshead_speed_mm_min=0.1–400; stroke_mm=200–750; vertical_test_space_mm=680–1350; specimen_diameter_mm=4–70; specimen_thickness_mm=0–70 | limited |

## Sensors Unlimited (`sensors-unlimited`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [sensors-unlimited-swir-cameras](equipment/sensors-unlimited/sensors-unlimited-swir-cameras.json) | 계열 | high_speed_swir_camera |  | – | – | resolution_pixels=81920–1310720; wavelength_nm=500–1700; frame_rate_fps=30, 60; pixel_pitch_um=12.5 | limited |

## Sentek Dynamics (`sentek-dynamics`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [sentek-dynamics-bt-bench-top-shakers](equipment/sentek-dynamics/sentek-dynamics-bt-bench-top-shakers.json) | 계열 | vibration_shaker | vibration_sine_random | – | – | force_N=20–440; frequency_Hz=0–15000; displacement_mm=5, 20; acceleration_g=≤100; payload_kg=≤2.5 | limited |
| [sentek-dynamics-e-series-shakers](equipment/sentek-dynamics/sentek-dynamics-e-series-shakers.json) | 계열 | vibration_shaker | vibration_sine_random, mechanical_shock | 196–392 | – | force_random_kN=196–274; force_shock_kN=392–784; frequency_Hz=5–2200; displacement_mm=51; acceleration_g=≤100; payload_kg=2000–4000 | limited |
| [sentek-dynamics-h-series-shakers](equipment/sentek-dynamics/sentek-dynamics-h-series-shakers.json) | 계열 | vibration_shaker | vibration_sine_random, mechanical_shock | 63.7–156.8 | – | force_random_kN=63.7–156.8; force_shock_kN=127.4–313.6; frequency_Hz=5–2500; displacement_mm=51; acceleration_g=≤100; payload_kg=1000–2000 | limited |
| [sentek-dynamics-l-series-shakers](equipment/sentek-dynamics/sentek-dynamics-l-series-shakers.json) | 계열 | vibration_shaker | vibration_sine_random, mechanical_shock | 0.98–9.8 | – | force_random_kN=0.98–9.8; force_shock_kN=1.96–19.6; frequency_Hz=5–5000; displacement_mm=25, 40, 51; acceleration_g=≤100; payload_kg=70–200 | limited |
| [sentek-dynamics-m-series-shakers](equipment/sentek-dynamics/sentek-dynamics-m-series-shakers.json) | 계열 | vibration_shaker | vibration_sine_random, mechanical_shock | 14.7–73.5 | – | force_random_kN=14.7–73.5; force_shock_kN=29.4–147; frequency_Hz=2–3000; displacement_mm=51; acceleration_g=≤100; payload_kg=300–1000 | limited |
| [sentek-dynamics-p-series-shakers](equipment/sentek-dynamics/sentek-dynamics-p-series-shakers.json) | 계열 | vibration_shaker | vibration_sine_random, mechanical_shock | 34.3–78.4 | – | force_random_kN=24–78.4; force_shock_kN=68.6–156.8; frequency_Hz=2–3000; displacement_mm=51; acceleration_g=≤150; payload_kg=500–800 | limited |
| [sentek-dynamics-sm-pv-shock-machines](equipment/sentek-dynamics/sentek-dynamics-sm-pv-shock-machines.json) | 계열 | shock_test_machine | mechanical_shock | – | – | acceleration_g=10–750; pulse_duration_ms=1.5–60; payload_kg=50–1000; table_size_mm=500–1200 | limited |
| [sentek-dynamics-t-series-long-stroke-shakers](equipment/sentek-dynamics/sentek-dynamics-t-series-long-stroke-shakers.json) | 계열 | vibration_shaker | vibration_sine_random, mechanical_shock | 29.4–52.9 | – | force_random_kN=29.4–52.9; force_shock_kN=58.8–105.8; frequency_Hz=5–2300; displacement_mm=100; acceleration_g=≤80; payload_kg=500–800 | limited |

## SETARAM (KEP Technologies) (`setaram`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [setaram-themys](equipment/setaram/setaram-themys.json) | 계열 | sta | tga, dsc, tma | – | ≤2400 | pressure_bar=≤150; heating_rate_K_min=0.01–600; balance_resolution_ug=0.00059–0.2 | catalog |

## Shimadzu (`shimadzu`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [shimadzu-ag-xplus](equipment/shimadzu/shimadzu-ag-xplus.json) | 계열 | universal_testing_machine | tensile, flexure, compression, peel | – | -180.0–320.0 |  | catalog |
| [shimadzu-ags-v](equipment/shimadzu/shimadzu-ags-v.json) | 계열 | universal_testing_machine | tensile, compression, flexure, peel, tear, friction_coefficient | 0.001–10 | – | crosshead_speed_mm_min=0.0005–1500; return_speed_mm_min=≤1650; vertical_test_space_mm=≤1180; horizontal_test_space_mm=425; data_rate_Hz=≤5000 | catalog |
| [shimadzu-ags-x](equipment/shimadzu/shimadzu-ags-x.json) | 계열 | universal_testing_machine | tensile, compression, flexure, shear, peel, tear | 0.001–300 | -70–1100 (부속) | crosshead_speed_mm_min=0.001–1600; vertical_test_space_mm=1200–1475; horizontal_test_space_mm=425–600; data_rate_Hz=≤1000; humidity_pct=40–95 | catalog |
| [shimadzu-ags-x-materialtwin](equipment/shimadzu/shimadzu-ags-x-materialtwin.json) | 계열 (보탬→shimadzu-ags-x) | universal_testing_machine | tensile, compression, flexure, shear, peel, tear | – | – |  | catalog |
| [shimadzu-agx-v2](equipment/shimadzu/shimadzu-agx-v2.json) | 계열 | universal_testing_machine | tensile, compression, flexure, shear, peel, tear, creep, relaxation | 0.01–600 | -70–1100 (부속) | crosshead_speed_mm_min=5e-05–3000; vertical_test_space_mm=180–2325; horizontal_test_space_mm=420–790; frame_stiffness_kN_mm=60–700; data_rate_Hz=≤10000 | catalog |
| [shimadzu-ceramics-bending-test-jig](equipment/shimadzu/shimadzu-ceramics-bending-test-jig.json) | **부속** | grip_fixture | flexure | ≤5 | – |  | limited |
| [shimadzu-contact-extensometers-sie-dses-dt-aeh](equipment/shimadzu/shimadzu-contact-extensometers-sie-dses-dt-aeh.json) | **센서** | extensometer | tensile, flexure | – | – |  | limited |
| [shimadzu-dsc-60-plus](equipment/shimadzu/shimadzu-dsc-60-plus.json) | 계열 | dsc | dsc | – | -140–600 | heat_flow_mW=≤150 | catalog |
| [shimadzu-dtg-60](equipment/shimadzu/shimadzu-dtg-60.json) | 계열 | sta | tga | – | ≤1500 | balance_resolution_ug=0.1 | catalog |
| [shimadzu-duh-211](equipment/shimadzu/shimadzu-duh-211.json) | 계열 | instrumented_indentation | instrumented_indentation, hardness_vickers, hardness_knoop | – | – | indentation_force_mN=0.1–1961; displacement_um=0–100; specimen_height_mm=≤60; stage_travel_mm=25×25 | catalog |
| [shimadzu-emt](equipment/shimadzu/shimadzu-emt.json) | 계열 | electrodynamic_fatigue | fatigue | – | – | dynamic_force_kN=1, 5; frequency_Hz=≤200; stroke_mm=60, 100 | limited |
| [shimadzu-ez-test](equipment/shimadzu/shimadzu-ez-test.json) | 계열 | universal_testing_machine | tensile, compression, creep | 0.001–5 | – | crosshead_speed_mm_min=0.001–2000 | catalog |
| [shimadzu-foam-rubber-compression-test-jig](equipment/shimadzu/shimadzu-foam-rubber-compression-test-jig.json) | **부속** | grip_fixture | compression | ≤1 | 0–40 | specimen_diameter_mm=≤200 | limited |
| [shimadzu-high-and-low-temperature-test-devices](equipment/shimadzu/shimadzu-high-and-low-temperature-test-devices.json) | **부속** | furnace | tensile, flexure, compression | – | ≤1500 |  | limited |
| [shimadzu-hmv-g](equipment/shimadzu/shimadzu-hmv-g.json) | 계열 | vickers_knoop_hardness | hardness_vickers, hardness_knoop | – | – | test_load_gf=1–2000; hardness_scales=HV, HK | limited |
| [shimadzu-hydraulic-flat-grips](equipment/shimadzu/shimadzu-hydraulic-flat-grips.json) | **부속** | grip_fixture | tensile | 10–600 | – | width_mm=≤85; pressure_MPa=≤70 | limited |
| [shimadzu-manual-screw-flat-grips](equipment/shimadzu/shimadzu-manual-screw-flat-grips.json) | **부속** | grip_fixture | tensile | – | -70–320 | force_N=10–5000; specimen_thickness_mm=≤16 | limited |
| [shimadzu-mmt](equipment/shimadzu/shimadzu-mmt.json) | 계열 | electrodynamic_fatigue | fatigue | – | – | dynamic_force_kN=0.01–0.5; frequency_Hz=≤100; stroke_mm=4, 20 | limited |
| [shimadzu-non-shift-wedge-grips](equipment/shimadzu/shimadzu-non-shift-wedge-grips.json) | **부속** | grip_fixture | tensile | 5–300 | – | pressure_MPa=≤21 | limited |
| [shimadzu-pantograph-and-eccentric-roller-grips](equipment/shimadzu/shimadzu-pantograph-and-eccentric-roller-grips.json) | **부속** | grip_fixture | tensile | – | – | force_N=100–5000 | limited |
| [shimadzu-pcb-bending-test-jig](equipment/shimadzu/shimadzu-pcb-bending-test-jig.json) | **부속** | grip_fixture | flexure, fatigue | – | – |  | limited |
| [shimadzu-pneumatic-flat-grips](equipment/shimadzu/shimadzu-pneumatic-flat-grips.json) | **부속** | grip_fixture | tensile | – | -70–200 | force_N=50–10000; pressure_MPa=0.2–0.7 | limited |
| [shimadzu-servopulser-ehf-e](equipment/shimadzu/shimadzu-servopulser-ehf-e.json) | 계열 | servohydraulic_fatigue | fatigue | – | – | dynamic_force_kN=50–200; static_force_kN=60–240; stroke_mm=50, 100 | limited |
| [shimadzu-servopulser-ehf-l](equipment/shimadzu/shimadzu-servopulser-ehf-l.json) | 계열 | servohydraulic_fatigue | fatigue | – | – | dynamic_force_kN=5–20; static_force_kN=6–24; stroke_mm=50, 100 | limited |
| [shimadzu-servopulser-ehf-u](equipment/shimadzu/shimadzu-servopulser-ehf-u.json) | 계열 | servohydraulic_fatigue | fatigue | – | – | dynamic_force_kN=50–200; static_force_kN=60–240; stroke_mm=50, 100 | limited |
| [shimadzu-servopulser-fatigue-grips-and-jigs](equipment/shimadzu/shimadzu-servopulser-fatigue-grips-and-jigs.json) | **부속** | grip_fixture | fatigue, tensile, compression, fracture_toughness | – | -196–300 | dynamic_force_kN=5–250 | limited |
| [shimadzu-ssg-strain-gauge-extensometers](equipment/shimadzu/shimadzu-ssg-strain-gauge-extensometers.json) | **센서** | extensometer | tensile | – | 5–40 | gauge_length_mm=10–50; displacement_mm=0.1–5 | limited |
| [shimadzu-thc-temperature-humidity-chamber](equipment/shimadzu/shimadzu-thc-temperature-humidity-chamber.json) | **부속** | environmental_chamber | tensile, compression, flexure, damp_heat | – | – |  | limited |
| [shimadzu-thermostatic-chambers-tcr-tcl-tce](equipment/shimadzu/shimadzu-thermostatic-chambers-tcr-tcl-tce.json) | **부속** | environmental_chamber | tensile, compression, flexure | – | -70–300 | temperature_fluctuation_degC=≤1.5; inner_mm=– | limited |
| [shimadzu-trapezium-x-software](equipment/shimadzu/shimadzu-trapezium-x-software.json) | software | accessory |  | – | – |  | limited |
| [shimadzu-trviewx-video-extensometer](equipment/shimadzu/shimadzu-trviewx-video-extensometer.json) | **센서** | extensometer | tensile, compression, flexure | – | – | field_of_view_mm=120–240; operating_temperature_degC=5–35 | limited |
| [shimadzu-uh-x-fx](equipment/shimadzu/shimadzu-uh-x-fx.json) | 계열 | hydraulic_utm | tensile, compression, flexure | 200–4000 | – | crosshead_speed_mm_min=0.1–100; stroke_mm=200–350; grip_span_mm=720–1150; specimen_diameter_mm=8–120; specimen_thickness_mm=0–120 | catalog |
| [shimadzu-uv-2600-2700](equipment/shimadzu/shimadzu-uv-2600-2700.json) | 계열 | optical_spectrometer | optical_spectroscopy | – | – |  | catalog |
| [shimadzu-xray-ct](equipment/shimadzu/shimadzu-xray-ct.json) | 계열 | xray_inspection | xray_void_inspection | – | – | tube_voltage_kV=160, 225; tube_current_mA=≤1.2; tube_power_W=≤135; sample_weight_kg=≤10 | limited |
| [shimadzu-xslicer](equipment/shimadzu/shimadzu-xslicer.json) | 계열 | xray_inspection | xray_void_inspection | – | – | tube_voltage_kV=90–160; tube_current_mA=≤0.25; tube_power_W=10–16; spatial_resolution_um=≥1; sample_size_mm=≤470; sample_weight_kg=≤5; operating_temperature_deg | limited |

## Shinyei Testing Machinery (`shinyei`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [shinyei-drop-shock-testers](equipment/shinyei/shinyei-drop-shock-testers.json) | 계열 | drop_tester | free_fall_drop, mechanical_shock | – | – | payload_kg=–; drop_height_mm=– | limited |

## Siemens Digital Industries (Simcenter) (`siemens`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [siemens-simcenter-scadas](equipment/siemens/siemens-simcenter-scadas.json) | 계열 | mechanical_dynamics |  | – | – |  | limited |
| [siemens-t3ster](equipment/siemens/siemens-t3ster.json) | 기종 | thermal_transient_tester | thermal_resistance | – | – | time_resolution_us=≥1; measurement_channels=≤8 | catalog |

## SIGLENT Technologies (`siglent`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [siglent-sds1000x-e](equipment/siglent/siglent-sds1000x-e.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=100000000–200000000; sample_rate_Sa_s=≤1000000000; record_length_pts=7000000–14000000; channels=2, 4; display_size_in=7; logic_channel_count=16 | limited |
| [siglent-sds2000x-hd](equipment/siglent/siglent-sds2000x-hd.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=100000000–350000000; sample_rate_Sa_s=≤2000000000; record_length_pts=≤200000000; channels=4; logic_channel_count=16; adc_resolution_bit=12; display | limited |
| [siglent-sds2000x-plus](equipment/siglent/siglent-sds2000x-plus.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=100000000–350000000; sample_rate_Sa_s=≤2000000000; record_length_pts=≤200000000; channels=2, 4; display_size_in=10.1; logic_channel_count=16 | limited |
| [siglent-sds3000x-hd](equipment/siglent/siglent-sds3000x-hd.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=350000000–1000000000; sample_rate_Sa_s=≤4000000000; record_length_pts=≤400000000; channels=4; adc_resolution_bit=12; logic_channel_count=16; displa | limited |

## Spectral Dynamics, Inc. (`spectral-dynamics`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [spectral-dynamics-air-cooled-shakers](equipment/spectral-dynamics/spectral-dynamics-air-cooled-shakers.json) | 계열 | vibration_shaker | vibration_sine_random | 0.5–68.64 | – | displacement_mm=20–76; acceleration_g=≤115; velocity_m_s=≤2; payload_kg=20–1000 | limited |
| [spectral-dynamics-vibration-controllers](equipment/spectral-dynamics/spectral-dynamics-vibration-controllers.json) | 계열 | mechanical_dynamics | vibration_sine_random, mechanical_shock | – | – | channels=4–588; adc_resolution_bit=24; dynamic_range_dB=≥110; data_rate_Hz=≤262144 | limited |
| [spectral-dynamics-water-cooled-shakers](equipment/spectral-dynamics/spectral-dynamics-water-cooled-shakers.json) | 계열 | vibration_shaker | vibration_sine_random | 59.0–350.0 | – | displacement_mm=63–100; acceleration_g=≤100; velocity_m_s=≤2; payload_kg=500–4000 | limited |

## Stable Micro Systems (`stable-micro-systems`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [sms-ta-xt-plus](equipment/stable-micro-systems/sms-ta-xt-plus.json) | 기종 | texture_analyser | texture, compression, tensile, puncture, peel | ≤0.5 | -10–80 | crosshead_speed_mm_min=0.6–2400; crosshead_travel_mm=1–295 | limited |
| [sms-texture-analyser-probes-and-attachments](equipment/stable-micro-systems/sms-texture-analyser-probes-and-attachments.json) | **부속** | accessory | texture, compression, tensile | – | – |  | limited |

## Struers (`struers`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [struers-duramin-40](equipment/struers/struers-duramin-40.json) | 계열 | vickers_knoop_hardness | hardness_vickers, hardness_knoop, hardness_brinell | – | – | test_load_gf=1–62500; hardness_scales=HV, HK, HBW | catalog |

## Suga Test Instruments Co., Ltd. (`suga`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [suga-sunshine-weather-meters](equipment/suga/suga-sunshine-weather-meters.json) | 계열 | weathering_tester | accelerated_weathering | – | – |  | limited |
| [suga-xenon-weather-meters](equipment/suga/suga-xenon-weather-meters.json) | 계열 | weathering_tester | accelerated_weathering | – | – | irradiance_W_m2=25–180 | limited |

## TA Instruments (`ta-instruments`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [ta-electroforce](equipment/ta-instruments/ta-electroforce.json) | 계열 | electrodynamic_fatigue | fatigue, dma, tensile, compression, torsion, flexure | – | -150–600 | force_N=0.002–15000; stroke_mm=5–150; frequency_Hz=1e-05–300; torque_Nm=5.6, 14, 25, 49, 70 | catalog |
| [ta-instruments-ar-rheometer](equipment/ta-instruments/ta-instruments-ar-rheometer.json) | 계열 | rotational_rheometer | shear, creep, dma | – | -160.0–600.0 |  | catalog |
| [ta-instruments-dilatometers](equipment/ta-instruments/ta-instruments-dilatometers.json) | 계열 | dilatometer | dilatometry | – | ≤1700 |  | limited |
| [ta-instruments-discovery-dsc](equipment/ta-instruments/ta-instruments-discovery-dsc.json) | 계열 | dsc | dsc | – | -180–725 | accuracy_degC=≤0.025 | catalog |
| [ta-instruments-discovery-dsc-web](equipment/ta-instruments/ta-instruments-discovery-dsc-web.json) | 계열 (보탬→ta-instruments-discovery-dsc) | dsc | dsc | – | – |  | limited |
| [ta-instruments-discovery-hybrid-rheometer](equipment/ta-instruments/ta-instruments-discovery-hybrid-rheometer.json) | 계열 | rotational_rheometer | rheology_rotational | – | – | torque_mNm=≤200; frequency_Hz=1e-07–100; angular_velocity_rad_s=0–300; force_N=≤50 | catalog |
| [ta-instruments-discovery-light-flash](equipment/ta-instruments/ta-instruments-discovery-light-flash.json) | 계열 | thermal_conductivity | thermal_conductivity | – | ≤1600 | thermal_diffusivity_mm2_s=0.01–1000; thermal_conductivity_W_mK=0.1–2000; specimen_thickness_mm=≤10; specimen_diameter_mm=8, 10, 12.7, 15.9, 25.4 | catalog |
| [ta-instruments-discovery-sdt-650](equipment/ta-instruments/ta-instruments-discovery-sdt-650.json) | 계열 | sta | tga, dsc | – | ≤1500 |  | limited |
| [ta-instruments-discovery-tga](equipment/ta-instruments/ta-instruments-discovery-tga.json) | 계열 | tga | tga | – | ≤1200 | heating_rate_K_min=0.1–500; cooling_rate_K_min=–; sample_mass_mg=≤750; balance_resolution_ug=≤0.001 | catalog |
| [ta-instruments-discovery-tga-materialtwin](equipment/ta-instruments/ta-instruments-discovery-tga-materialtwin.json) | 계열 (보탬→ta-instruments-discovery-tga) | tga | tga | – | ≤1200.0 |  | catalog |
| [ta-instruments-discovery-tma-450](equipment/ta-instruments/ta-instruments-discovery-tma-450.json) | 계열 | tma | tma | – | -150–1000 |  | limited |
| [ta-instruments-dma](equipment/ta-instruments/ta-instruments-dma.json) | 계열 | dma | dma | – | -150–600 | force_N=0.0001–18; frequency_Hz=0.01–200; heating_rate_K_min=0.1–20; cooling_rate_K_min=0.1–10; displacement_um=0.5–10000 | catalog |
| [ta-instruments-rsa-g2](equipment/ta-instruments/ta-instruments-rsa-g2.json) | 계열 | dma | dma | – | -150–600 (부속) | force_N=0.0005–35; frequency_Hz=2e-05–100; heating_rate_K_min=0.1–60; cooling_rate_K_min=0.1–60; displacement_mm=5e-05–1.5 | catalog |
| [ta-instruments-sdt-q600](equipment/ta-instruments/ta-instruments-sdt-q600.json) | 계열 | sta | tga, dsc | – | ≤1500 | heating_rate_K_min=0.1–100; sample_volume_uL=40, 90, 110 | catalog |
| [ta-instruments-vti-sa-sorption](equipment/ta-instruments/ta-instruments-vti-sa-sorption.json) | 계열 | vapor_sorption_analyzer | vapor_sorption, tga | – | 5–150 | humidity_pct=–; sample_mass_mg=≤5000; balance_resolution_ug=≥0.01 | catalog |

## Taber Industries (`taber`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [taber-linear-abraser-5770](equipment/taber/taber-linear-abraser-5770.json) | 기종 | abrasion_tester | abrasion | – | – | cycle_rate_cpm=2–75; stroke_mm=5.08–101.6; load_g=60–2100 | limited |
| [taber-reciprocating-abraser-5900](equipment/taber/taber-reciprocating-abraser-5900.json) | 기종 | abrasion_tester | abrasion | – | – | stroke_mm=6–155; cycle_rate_cpm=3–75; load_N=1, 2, 2.5, 5, 10, 24; specimen_size_mm=≤278; stations=≤3 | limited |
| [taber-rotary-abraser-1700-1750](equipment/taber/taber-rotary-abraser-1700-1750.json) | 계열 | abrasion_tester | abrasion | – | – | rotation_rpm=60, 72; load_g=250, 500, 1000; specimen_thickness_mm=≤40; specimen_size_mm=≤100; stations=1, 2 | limited |
| [taber-rotary-abraser-5135-5155](equipment/taber/taber-rotary-abraser-5135-5155.json) | 계열 | abrasion_tester | abrasion | – | – | rotation_rpm=60, 72; load_g=250, 500, 1000; specimen_thickness_mm=≤40; stations=1, 2 | catalog |
| [taber-rotary-abraser-accessories](equipment/taber/taber-rotary-abraser-accessories.json) | **부속** | accessory | abrasion | – | – | load_g=75–1000 | limited |
| [taber-scratch-testers](equipment/taber/taber-scratch-testers.json) | 계열 | scratch_hardness_tester | scratch_pencil_hardness | – | – | load_N=2–25; load_g=0–1500; rotation_rpm=0.6, 5; specimen_thickness_mm=≤22 | limited |

## Techno Optis (former Topcon Technohouse) (`techno-optis`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [techno-optis-bm-series](equipment/techno-optis/techno-optis-bm-series.json) | 계열 | display_color_analyzer | photometry_colorimetry | – | – | luminance_cd_m2=5e-05–28000000; measuring_angle_deg=3, 2, 1, 0.2, 0.1; measurement_time_s=0.5–2 | limited |
| [techno-optis-sr-5-series](equipment/techno-optis/techno-optis-sr-5-series.json) | 계열 | spectroradiometer | photometry_colorimetry | – | – | wavelength_nm=380–780; measuring_angle_deg=2, 1, 0.2, 0.1; luminance_cd_m2=0.0001–500000000; spectral_bandwidth_nm=≤5 | limited |
| [techno-optis-sr-5100](equipment/techno-optis/techno-optis-sr-5100.json) | 계열 | spectroradiometer | photometry_colorimetry | – | – | resolution_pixels=≤5013504; wavelength_nm=380–780; luminance_cd_m2=0.005–17000000000; chromaticity_accuracy_xy=0.0035–0.005 | limited |

## Tekscan, Inc. (`tekscan`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [tekscan-flexiforce](equipment/tekscan/tekscan-flexiforce.json) | **센서** | force_pressure_sensor |  | – | – | force_N=4.4–2224; response_time_ms=≤0.005; operating_temperature_degC=-40–240 | limited |
| [tekscan-i-scan](equipment/tekscan/tekscan-i-scan.json) | 계열 | force_pressure_sensor |  | – | – | pressure_bar=≤1700; data_rate_Hz=≤20000; spatial_resolution_um=≥600; inspection_area_mm=3–1768; operating_temperature_degC=≤200 | catalog |

## Tektronix (`tektronix`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [tektronix-2-series-mso](equipment/tektronix/tektronix-2-series-mso.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=70000000–500000000; sample_rate_Sa_s=≤2500000000; record_length_pts=≤10000000; channels=2, 4; logic_channel_count=16; display_size_in=10 | limited |
| [tektronix-3-series-mdo](equipment/tektronix/tektronix-3-series-mdo.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=100000000–1000000000; sample_rate_Sa_s=≤5000000000; record_length_pts=≤10000000; channels=2, 4; logic_channel_count=16; display_size_in=11.6 | limited |
| [tektronix-4-series-b-mso](equipment/tektronix/tektronix-4-series-b-mso.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=200000000–1500000000; sample_rate_Sa_s=≤6250000000; record_length_pts=31250000–62500000; channels=4, 6; logic_channel_count=32, 48; adc_resolution_ | limited |
| [tektronix-5-series-b-mso](equipment/tektronix/tektronix-5-series-b-mso.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=350000000–2000000000; sample_rate_Sa_s=≤6250000000; record_length_pts=62500000–500000000; channels=4, 6, 8; logic_channel_count=32, 48, 64; adc_res | limited |
| [tektronix-6-series-b-mso](equipment/tektronix/tektronix-6-series-b-mso.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=1000000000–10000000000; sample_rate_Sa_s=25000000000–50000000000; record_length_pts=62500000–1000000000; channels=4, 6, 8; logic_channel_count=32,  | limited |
| [tektronix-7-series-dpo](equipment/tektronix/tektronix-7-series-dpo.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=8000000000–25000000000; sample_rate_Sa_s=≤125000000000; record_length_pts=≤2000000000; channels=4, 8; adc_resolution_bit=12 | limited |
| [tektronix-afg1000](equipment/tektronix/tektronix-afg1000.json) | 계열 | signal_generator |  | – | – | output_frequency_Hz=1e-06–60000000; channels=2; sample_rate_Sa_s=125000000, 300000000; dac_resolution_bit=14; output_voltage_V=0.001–10; waveform_memory_pts=800 | limited |
| [tektronix-afg31000](equipment/tektronix/tektronix-afg31000.json) | 계열 | signal_generator |  | – | – | output_frequency_Hz=≤250000000; channels=1, 2; sample_rate_Sa_s=250000000–2000000000; dac_resolution_bit=14; output_voltage_V=0.001–10; waveform_memory_pts=1600 | catalog |
| [tektronix-awg5200](equipment/tektronix/tektronix-awg5200.json) | 계열 | signal_generator |  | – | – | output_frequency_Hz=≤4000000000; bandwidth_Hz=≤2000000000; channels=2, 4, 8; sample_rate_Sa_s=300–10000000000; dac_resolution_bit=16; rf_output_level_dBm=-85–10 | catalog |
| [tektronix-dpo70000sx](equipment/tektronix/tektronix-dpo70000sx.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=33000000000–70000000000; sample_rate_Sa_s=100000000000–200000000000; record_length_pts=≤1000000000 | limited |
| [tektronix-mdo3000](equipment/tektronix/tektronix-mdo3000.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=100000000–200000000; sample_rate_Sa_s=≤2500000000; record_length_pts=≤10000000; channels=4; logic_channel_count=16 | limited |
| [tektronix-mdo4000c](equipment/tektronix/tektronix-mdo4000c.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=200000000–1000000000; sample_rate_Sa_s=2500000000–5000000000; record_length_pts=≤20000000; channels=4; logic_channel_count=16; adc_resolution_bit=8 | limited |
| [tektronix-mso-dpo70000dx](equipment/tektronix/tektronix-mso-dpo70000dx.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=8000000000–33000000000; channels=4; logic_channel_count=16; sample_rate_Sa_s=50000000000–100000000000; record_length_pts=62500000–1000000000 | limited |
| [tektronix-tbs1000c](equipment/tektronix/tektronix-tbs1000c.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=50000000–200000000; sample_rate_Sa_s=≤1000000000; record_length_pts=≤20000; channels=2; display_size_in=7 | limited |
| [tektronix-tbs2000b](equipment/tektronix/tektronix-tbs2000b.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=70000000–200000000; sample_rate_Sa_s=≤2000000000; record_length_pts=≤5000000; channels=2, 4; display_size_in=9 | limited |

## Teledyne LeCroy (`teledyne-lecroy`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [teledyne-lecroy-hdo4000a](equipment/teledyne-lecroy/teledyne-lecroy-hdo4000a.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=200000000–1000000000; sample_rate_Sa_s=≤10000000000; record_length_pts=≤25000000; channels=4; logic_channel_count=16; adc_resolution_bit=12; displa | limited |
| [teledyne-lecroy-hdo6000b](equipment/teledyne-lecroy/teledyne-lecroy-hdo6000b.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=350000000–1000000000; sample_rate_Sa_s=≤10000000000; record_length_pts=50000000–250000000; channels=4; logic_channel_count=16; adc_resolution_bit=1 | limited |
| [teledyne-lecroy-wavemaster-8000hd](equipment/teledyne-lecroy/teledyne-lecroy-wavemaster-8000hd.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=20000000000–65000000000; sample_rate_Sa_s=160000000000–320000000000; record_length_pts=8000000000–16000000000; channels=4; adc_resolution_bit=12 | limited |
| [teledyne-lecroy-wavepro-hd](equipment/teledyne-lecroy/teledyne-lecroy-wavepro-hd.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=2500000000–8000000000; sample_rate_Sa_s=≤20000000000; record_length_pts=50000000–5000000000; channels=4; adc_resolution_bit=12 | limited |
| [teledyne-lecroy-waverunner-8000hd](equipment/teledyne-lecroy/teledyne-lecroy-waverunner-8000hd.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=350000000–2000000000; sample_rate_Sa_s=≤10000000000; record_length_pts=≤5000000000; channels=8; adc_resolution_bit=12; display_size_in=15.6 | limited |
| [teledyne-lecroy-wavesurfer-4000hd](equipment/teledyne-lecroy/teledyne-lecroy-wavesurfer-4000hd.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=200000000–1000000000; sample_rate_Sa_s=≤2500000000; record_length_pts=≤25000000; channels=4; adc_resolution_bit=12 | limited |

## Teseq / AMETEK CTS (`teseq`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [teseq-nsg-3060](equipment/teseq/teseq-nsg-3060.json) | 계열 | transient_generator | surge_eft_immunity | – | – | surge_voltage_kV=0.2–6.6; eft_voltage_kV=0.2–4.8; polarity=positive, negative; cdn_voltage_V=≤480; cdn_current_A=≤100 | catalog |
| [teseq-nsg-437-435](equipment/teseq/teseq-nsg-437-435.json) | 계열 | esd_simulator | esd_immunity | – | – | esd_voltage_kV=0.2–30; discharge_mode=contact, air; frequency_Hz=≤25 | catalog |
| [teseq-nsg-438](equipment/teseq/teseq-nsg-438.json) | 기종 | esd_simulator | esd_immunity | – | – | esd_voltage_kV=0.2–30.0; frequency_Hz=0.5–25; discharge_mode=contact, air; polarity=positive, negative, alternating | catalog |

## Testo (`testo`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [testo-865s-872s](equipment/testo/testo-865s-872s.json) | 계열 | thermal_imager | thermography | – | -30–650 | ir_resolution_pixels=19200–76800; thermal_sensitivity_degC=0.05–0.1 | limited |
| [testo-883](equipment/testo/testo-883.json) | 계열 | thermal_imager | thermography | – | – | ir_resolution_pixels=≤76800; thermal_sensitivity_degC=≤0.04 | limited |
| [testo-890](equipment/testo/testo-890.json) | 계열 | thermal_imager | thermography | – | -30–650 | ir_resolution_pixels=≤307200; thermal_sensitivity_degC=≤0.04; wavelength_nm=7500–14000 | catalog |

## Testometric (`testometric`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [testometric-extensometers](equipment/testometric/testometric-extensometers.json) | **센서** | extensometer | tensile | – | – | displacement_mm=≤850; field_of_view_mm=≤100 | limited |
| [testometric-m500](equipment/testometric/testometric-m500.json) | 계열 | universal_testing_machine | tensile, compression, flexure, shear, peel, tear, creep, fatigue | 0.005–100 | – | crosshead_speed_mm_min=0.001–1000; vertical_test_space_mm=1180–1300; horizontal_test_space_mm=420; data_rate_Hz=≤12000 | catalog |
| [testometric-tensile-grips](equipment/testometric/testometric-tensile-grips.json) | **부속** | grip_fixture | tensile | – | – | force_N=500–300000 | limited |
| [testometric-test-fixtures](equipment/testometric/testometric-test-fixtures.json) | **부속** | grip_fixture | flexure, puncture, peel, shear, tear, burst_pressure, compression | ≤100 | – | hdt_span_mm=50–600 | limited |

## Thermo Fisher Scientific (HAAKE) (`thermo-fisher`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [thermo-haake-mars](equipment/thermo-fisher/thermo-haake-mars.json) | 계열 | rotational_rheometer | rheology_rotational, dma, friction_wear_tribo | – | -150–600 | torque_mNm=2e-06–200; rotation_rpm=1e-08–4500; frequency_Hz=1e-06–100; force_N=0.01–50 | catalog |
| [thermo-nexsa-g2](equipment/thermo-fisher/thermo-nexsa-g2.json) | 기종 | composition_spectrometer | composition_analysis | – | – |  | catalog |

## Thermotron Industries (`thermotron`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [thermotron-ats](equipment/thermotron/thermotron-ats.json) | 계열 | thermal_shock_chamber | thermal_shock, temperature_cycling | – | – |  | limited |
| [thermotron-fa-altitude-chambers](equipment/thermotron/thermotron-fa-altitude-chambers.json) | 계열 | altitude_chamber | altitude_low_pressure, temperature_cycling, damp_heat | – | -73–177 | chamber_pressure_kPa=≥1.07; altitude_m=≤30480; humidity_pct=20–95; chamber_volume_L=131–2718 | catalog |
| [thermotron-se-s-series](equipment/thermotron/thermotron-se-s-series.json) | 계열 | climatic_chamber | damp_heat, temperature_cycling | – | – | humidity_pct=10–98 | limited |
| [thermotron-se-s-series-models](equipment/thermotron/thermotron-se-s-series-models.json) | 계열 (보탬→thermotron-se-s-series) | climatic_chamber | damp_heat, temperature_cycling | – | – | chamber_volume_L=25–2945 | limited |

## Tinius Olsen (`tinius-olsen`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [tinius-olsen-100r-100s-extensometers](equipment/tinius-olsen/tinius-olsen-100r-100s-extensometers.json) | **센서** | extensometer | tensile | – | – | displacement_mm=≤970; gauge_length_mm=10–50; specimen_thickness_mm=≤10 | limited |
| [tinius-olsen-600ls-laser-extensometer](equipment/tinius-olsen/tinius-olsen-600ls-laser-extensometer.json) | **센서** | extensometer | tensile | – | -70–300 | displacement_mm=≤600; gauge_length_mm=≥10; data_rate_Hz=≤660 | limited |
| [tinius-olsen-automatic-extensometers-ae900-aex](equipment/tinius-olsen/tinius-olsen-automatic-extensometers-ae900-aex.json) | **센서** | extensometer | tensile | – | – | displacement_mm=≤910; gauge_length_mm=10–500; displacement_um=≥0.01; operating_temperature_degC=0–50 | limited |
| [tinius-olsen-environmental-chambers](equipment/tinius-olsen/tinius-olsen-environmental-chambers.json) | **부속** | environmental_chamber | tensile, compression, flexure | – | -150–600 | temperature_fluctuation_degC=≤2; test_room_height_mm=≤610; test_room_width_mm=≤250; test_room_depth_mm=≤245 | limited |
| [tinius-olsen-high-temperature-furnaces](equipment/tinius-olsen/tinius-olsen-high-temperature-furnaces.json) | **부속** | furnace | tensile, creep | – | ≤1400 | temperature_fluctuation_degC=≤5; heated_length_mm=110–300; bore_diameter_mm=≤90 | limited |
| [tinius-olsen-l-series](equipment/tinius-olsen/tinius-olsen-l-series.json) | 계열 | universal_testing_machine | tensile, compression, flexure, shear | 5–50 | – | crosshead_speed_mm_min=0.001–1000 | catalog |
| [tinius-olsen-lvdt-and-strain-gage-extensometers](equipment/tinius-olsen/tinius-olsen-lvdt-and-strain-gage-extensometers.json) | **센서** | extensometer | tensile, compression | – | -265–200 | gauge_length_mm=12.7–80; specimen_thickness_mm=1.6–75 | limited |
| [tinius-olsen-mp1200-melt-flow](equipment/tinius-olsen/tinius-olsen-mp1200-melt-flow.json) | 계열 | melt_flow_indexer | melt_flow | – | – | melt_temperature_degC=≤450; melt_load_kg=0.325–21.6 | catalog |
| [tinius-olsen-sl-series](equipment/tinius-olsen/tinius-olsen-sl-series.json) | 계열 | hydraulic_utm | tensile, compression, flexure, shear | 300–4500 | – | stroke_mm=152, 229; piston_speed_mm_min=0–76 | catalog |
| [tinius-olsen-st-series](equipment/tinius-olsen/tinius-olsen-st-series.json) | 계열 | universal_testing_machine | tensile, compression, flexure, shear, tear, peel | 1–300 | – | crosshead_speed_mm_min=0.0001–2500; vertical_test_space_mm=–; data_rate_Hz=≤1000 | catalog |
| [tinius-olsen-tensile-grips](equipment/tinius-olsen/tinius-olsen-tensile-grips.json) | **부속** | grip_fixture | tensile | ≤300 | – |  | limited |
| [tinius-olsen-test-fixtures](equipment/tinius-olsen/tinius-olsen-test-fixtures.json) | **부속** | grip_fixture | flexure, peel, friction_coefficient, shear | – | – |  | limited |
| [tinius-olsen-torsion-testers](equipment/tinius-olsen/tinius-olsen-torsion-testers.json) | 계열 | torsion_tester | torsion | – | – | torque_Nm=1000–30000; rotation_speed_deg_min=5–360; specimen_diameter_mm=≤127; specimen_length_mm=≤2286 | catalog |
| [tinius-olsen-uvx3d-video-extensometers](equipment/tinius-olsen/tinius-olsen-uvx3d-video-extensometers.json) | **센서** | extensometer | tensile, compression, flexure, shear, fatigue, torsion | – | – | field_of_view_mm=110–220; gauge_length_mm=10–200; data_rate_Hz=≤1000; displacement_um=≥0.5 | limited |
| [tinius-olsen-vector-extensometers](equipment/tinius-olsen/tinius-olsen-vector-extensometers.json) | **센서** | extensometer | tensile, compression, flexure, fatigue | – | – | field_of_view_mm=70–200; gauge_length_mm=6–180; data_rate_Hz=≤150; displacement_um=≥0.5 | limited |

## TIRA GmbH (`tira`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [tira-tiravib-5x-shakers](equipment/tira/tira-tiravib-5x-shakers.json) | 계열 | vibration_shaker | vibration_sine_random | – | – | force_N=40–200; frequency_Hz=2–8000; displacement_mm=≤25; velocity_m_s=≤1.5; acceleration_g=≤102; current_A=≤11.2 | catalog |
| [tira-tv-large-shakers](equipment/tira/tira-tv-large-shakers.json) | 계열 | vibration_shaker | vibration_sine_random, mechanical_shock | 22–300 | – | force_random_kN=17–270; force_shock_kN=66–900; frequency_Hz=5–3000; stroke_mm_pk_pk=50.8–76.2; acceleration_g=≤100; armature_diameter_mm=340, 440, 480, 590, 640 | limited |
| [tira-tv-medium-shakers](equipment/tira/tira-tv-medium-shakers.json) | 계열 | vibration_shaker | vibration_sine_random, mechanical_shock | 4–15 | – | frequency_Hz=2–4500; stroke_mm_pk_pk=50.8; acceleration_g=≤100 | limited |
| [tira-tv-small-shakers](equipment/tira/tira-tv-small-shakers.json) | 계열 | vibration_shaker | vibration_sine_random, mechanical_shock | – | – | force_N=9–2700; frequency_Hz=2–20000; stroke_mm_pk_pk=3–45; acceleration_g=≤100 | limited |

## TQC Sheen (Industrial Physics) (`tqc-sheen`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [tqc-sheen-coating-test-kits](equipment/tqc-sheen/tqc-sheen-coating-test-kits.json) | 계열 | scratch_hardness_tester | scratch_pencil_hardness, coating_adhesion | – | – | pencil_hardness_grade=8B, 7B, 6B, 5B, 4B, 3B, 2B, B; pencil_load_g=500, 750, 1000; pencil_angle_deg=45; cross_cut_squares=25, 100 | catalog |

## Unholtz-Dickie (`unholtz-dickie`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [unholtz-dickie-680c-calibrator](equipment/unholtz-dickie/unholtz-dickie-680c-calibrator.json) | 계열 | accessory | vibration_sine_random | – | – | frequency_Hz=2–10000; acceleration_g=≤75; velocity_m_s=≤1.3 | catalog |
| [unholtz-dickie-ls-thrusters](equipment/unholtz-dickie/unholtz-dickie-ls-thrusters.json) | 계열 | shock_test_machine | mechanical_shock, vibration_sine_random | 11–38 | – | stroke_mm=152–609; velocity_change_m_s=7.6–20; acceleration_g=≤400; table_size_mm=≤1219 | catalog |
| [unholtz-dickie-shakers](equipment/unholtz-dickie/unholtz-dickie-shakers.json) | 계열 | vibration_shaker | vibration_sine_random, mechanical_shock | 0.45–245 | – | frequency_Hz=≤5000; stroke_mm=≤76; acceleration_g=≤200; payload_kg=≤1818; velocity_m_s=≤3.5 | catalog |

## Uson (PAC) (`uson`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [uson-qualitek-mr](equipment/uson/uson-qualitek-mr.json) | 계열 | leak_tester | leak_rate, seal_strength | – | – | pressure_psi=≤500; flow_rate_ratio=–; channels=1 | catalog |
| [uson-sprint-leak-testers](equipment/uson/uson-sprint-leak-testers.json) | 계열 | leak_tester | leak_rate, seal_strength | – | – | pressure_psi=-15–500; leak_rate_mbar_L_s=–; channels=1–4; pressure_resolution_Pa=– | catalog |

## Viscom SE (`viscom`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [viscom-inline-axi](equipment/viscom/viscom-inline-axi.json) | 계열 | xray_inspection | xray_void_inspection | – | – | tube_voltage_kV=≤180; spatial_resolution_um=≥6; sample_size_mm=≤1400; sample_weight_kg=≤15 | limited |
| [viscom-manual-xray](equipment/viscom/viscom-manual-xray.json) | 계열 | xray_inspection | xray_void_inspection | – | – | tube_voltage_kV=20–210; spatial_resolution_um=≥4; magnification=≤2500; sample_weight_kg=≤25; specimen_diameter_mm=≤722 | limited |

## Vision Research (AMETEK) (`vision-research`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [vision-research-phantom-miro](equipment/vision-research/vision-research-phantom-miro.json) | 계열 | high_speed_swir_camera |  | – | – | frame_rate_fps=1380–1800; max_frame_rate_fps=≤325000 | limited |
| [vision-research-phantom-t-series](equipment/vision-research/vision-research-phantom-t-series.json) | 계열 | high_speed_swir_camera |  | – | – | frame_rate_fps=9350–24000; max_frame_rate_fps=≤525000 | limited |
| [vision-research-phantom-tmx](equipment/vision-research/vision-research-phantom-tmx.json) | 계열 | high_speed_swir_camera |  | – | – | frame_rate_fps=50725–76000; max_frame_rate_fps=≤1750000; min_exposure_time_s=≥9.5e-08 | limited |
| [vision-research-phantom-veo](equipment/vision-research/vision-research-phantom-veo.json) | 계열 | high_speed_swir_camera |  | – | – | resolution_pixels=≤4096000; frame_rate_fps=1100–10860 | limited |

## Walter + Bai AG (`walter-bai`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [walter-bai-lfv](equipment/walter-bai/walter-bai-lfv.json) | 계열 | servohydraulic_fatigue | fatigue, fracture_toughness, thermomechanical_fatigue, tensile, compression, flexure, relaxation | – | – | dynamic_force_kN=≤630 | limited |
| [walter-bai-lfv-e](equipment/walter-bai/walter-bai-lfv-e.json) | 계열 | electrodynamic_fatigue | fatigue, torsion | – | – | dynamic_force_kN=≤12 | limited |

## Waygate Technologies (Baker Hughes) (`waygate-technologies`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [waygate-technologies-phoenix-micromex-nanomex-neo](equipment/waygate-technologies/waygate-technologies-phoenix-micromex-nanomex-neo.json) | 계열 | xray_inspection | xray_void_inspection | – | – | tube_voltage_kV=160, 180; tube_power_W=≤20; feature_recognition_um=≥0.2; spatial_resolution_um=≥0.8; inspection_area_mm=≤610; sample_size_mm=≤680; sample_weight | catalog |
| [waygate-technologies-phoenix-vtomex](equipment/waygate-technologies/waygate-technologies-phoenix-vtomex.json) | 계열 | xray_inspection | xray_void_inspection | – | – | tube_voltage_kV=180, 240, 300, 450; tube_power_W=15–1500; feature_recognition_um=≥0.2; voxel_size_um=≥0.27; specimen_diameter_mm=≤500; specimen_height_mm=≤1000; | catalog |

## Weiss Technik (`weiss-technik`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [weiss-climeevent](equipment/weiss-technik/weiss-climeevent.json) | 계열 | climatic_chamber | damp_heat, temperature_cycling | – | -50–180 | humidity_pct=10–98 | limited |
| [weiss-dust-chamber-st](equipment/weiss-technik/weiss-dust-chamber-st.json) | 계열 | dust_chamber | dust_ingress | – | – |  | limited |
| [weiss-labevent](equipment/weiss-technik/weiss-labevent.json) | 계열 | climatic_chamber | damp_heat, temperature_cycling | – | -70–180 | humidity_pct=10–95; chamber_volume_L=16–210 | limited |
| [weiss-shockevent](equipment/weiss-technik/weiss-shockevent.json) | 계열 | thermal_shock_chamber | thermal_shock, temperature_cycling | – | -80–220 |  | catalog |
| [weiss-skyevent](equipment/weiss-technik/weiss-skyevent.json) | 계열 | altitude_chamber | altitude_low_pressure, temperature_cycling, damp_heat | – | -70–120 | chamber_pressure_kPa=≥0.5; altitude_m=≤13716; humidity_pct=15–95; chamber_volume_L=220–1500; heating_rate_K_min=≤2; cooling_rate_K_min=≤2; power_kW=28–52 | catalog |
| [weiss-tempevent](equipment/weiss-technik/weiss-tempevent.json) | 계열 | climatic_chamber | temperature_cycling | – | -70–180 | heating_rate_K_min=10–25; cooling_rate_K_min=10–25 | limited |
| [weiss-waterevent-swt](equipment/weiss-technik/weiss-waterevent-swt.json) | 계열 | water_ingress_tester | water_ingress | – | – | ipx_levels=–; oscillating_tube_radius_mm=200–800; chamber_volume_L=1015–5832; payload_kg=≤35 | catalog |

## WENZEL Group (`wenzel`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [wenzel-lh](equipment/wenzel/wenzel-lh.json) | 계열 | coordinate_measuring_machine |  | – | – | measuring_range_x_mm=650–2000; measuring_range_y_mm=750–5000; measuring_range_z_mm=500–1500 | limited |

## XYZTEC (`xyztec`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [xyztec-sigma](equipment/xyztec/xyztec-sigma.json) | 계열 | bond_tester | wire_bond_strength | – | – | shear_force_kgf=0.001–1000; stage_travel_mm=≤600; wafer_size_mm=≤300; data_rate_Hz=≤10000; position_resolution_nm=≥10 | limited |

## Yokogawa Test & Measurement (`yokogawa`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [yokogawa-dlm2000](equipment/yokogawa/yokogawa-dlm2000.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=200000000–500000000; channels=2, 4; logic_channel_count=8; sample_rate_Sa_s=≤2500000000; record_length_pts=≤250000000; display_size_in=8.4; adc_res | catalog |
| [yokogawa-dlm3000](equipment/yokogawa/yokogawa-dlm3000.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=200000000–500000000; channels=2, 4; logic_channel_count=8; record_length_pts=12500000–125000000 | limited |
| [yokogawa-dlm3000hd](equipment/yokogawa/yokogawa-dlm3000hd.json) | 계열 | oscilloscope |  | – | – | channels=4; logic_channel_count=8; bandwidth_Hz=350000000, 500000000; sample_rate_Sa_s=≤2500000000; record_length_pts=125000000–1000000000; adc_resolution_bit=1 | limited |
| [yokogawa-dlm5000](equipment/yokogawa/yokogawa-dlm5000.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=350000000–500000000; channels=4, 8; logic_channel_count=32; sample_rate_Sa_s=≤2500000000; record_length_pts=50000000–500000000; display_size_in=12. | limited |
| [yokogawa-dlm5000hd](equipment/yokogawa/yokogawa-dlm5000hd.json) | 계열 | oscilloscope |  | – | – | bandwidth_Hz=≤500000000; channels=4, 8; sample_rate_Sa_s=≤2500000000; record_length_pts=≤1000000000; adc_resolution_bit=12; logic_channel_count=16–32; display_s | limited |
| [yokogawa-scopecorder-dl950-dl350](equipment/yokogawa/yokogawa-scopecorder-dl950-dl350.json) | 계열 | dmm_daq |  | – | – | channels=≤160; data_rate_Hz=≤200000000 | limited |
| [yokogawa-smartdac-plus-gm-gp](equipment/yokogawa/yokogawa-smartdac-plus-gm-gp.json) | 계열 | dmm_daq |  | – | – | channels=≤450; data_interval_ms=≤1 | catalog |
| [yokogawa-wt5000](equipment/yokogawa/yokogawa-wt5000.json) | 기종 | power_analyzer | power_consumption | – | – | frequency_Hz=0.1–5000000; current_A=0.005–30; voltage_V=≥1.5; input_elements=≤7; harmonic_order=≤500 | catalog |

## YUASA SYSTEM Co., Ltd. (`yuasa-system`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [yuasa-system-face-plate-bending](equipment/yuasa-system/yuasa-system-face-plate-bending.json) | 계열 | component_life_tester | mechanical_endurance | – | – | cycle_rate_cpm=5–120; fold_angle_deg=0–180; bend_radius_mm=2.5–100; specimen_width_mm=≤70; force_N=≤100 | limited |
| [yuasa-system-folding](equipment/yuasa-system/yuasa-system-folding.json) | 계열 | component_life_tester | mechanical_endurance | – | – | cycle_rate_cpm=5–90; fold_angle_deg=0–180; bend_radius_mm=0–80; stroke_mm=≤60; specimen_thickness_mm=≤3; specimen_width_mm=≤300; stations=1, 2, 4 | limited |
| [yuasa-system-push-insertion](equipment/yuasa-system/yuasa-system-push-insertion.json) | 계열 | component_life_tester | mechanical_endurance | – | – | cycle_rate_cpm=10–120; stroke_mm=≤60; force_N=≤20 | limited |

## ZEISS (`zeiss`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [zeiss-aramis-3d-camera](equipment/zeiss/zeiss-aramis-3d-camera.json) | 계열 | dic_strain_measurement | tensile, compression, fatigue | – | – | field_of_view_mm=35–5100; data_rate_Hz=≤1000 | limited |
| [zeiss-aramis-adjustable](equipment/zeiss/zeiss-aramis-adjustable.json) | 계열 | dic_strain_measurement | tensile, compression, fatigue | – | – | field_of_view_mm=15–5000; data_rate_Hz=≤200000 | limited |
| [zeiss-axio-imager-2-materials](equipment/zeiss/zeiss-axio-imager-2-materials.json) | 계열 | optical_microscope | microscopy | – | – |  | limited |
| [zeiss-axioscope-materials](equipment/zeiss/zeiss-axioscope-materials.json) | 계열 | optical_microscope | microscopy | – | – | specimen_height_mm=≤380; stage_travel_mm=≤80; operating_temperature_degC=10–40 | catalog |
| [zeiss-contura](equipment/zeiss/zeiss-contura.json) | 계열 | coordinate_measuring_machine |  | – | – | measuring_range_x_mm=700–1200; measuring_range_y_mm=700–2400; measuring_range_z_mm=600–1000; specimen_mass_kg=730–1200 | limited |
| [zeiss-duramax](equipment/zeiss/zeiss-duramax.json) | 계열 | coordinate_measuring_machine |  | – | – | measuring_range_x_mm=500; measuring_range_y_mm=500; measuring_range_z_mm=500 | limited |
| [zeiss-gemini-fesem](equipment/zeiss/zeiss-gemini-fesem.json) | 기종 | electron_microscope | microscopy, composition_analysis | – | – |  | limited |
| [zeiss-micura](equipment/zeiss/zeiss-micura.json) | 계열 | coordinate_measuring_machine |  | – | – | specimen_mass_kg=≤730 | limited |
| [zeiss-o-inspect](equipment/zeiss/zeiss-o-inspect.json) | 계열 | coordinate_measuring_machine |  | – | – | measuring_range_x_mm=300–800; measuring_range_y_mm=200–600; measuring_range_z_mm=200–300 | limited |
| [zeiss-prismo](equipment/zeiss/zeiss-prismo.json) | 계열 | coordinate_measuring_machine |  | – | – | measuring_range_x_mm=700–1600; measuring_range_y_mm=900–4200; measuring_range_z_mm=500–1400 | limited |
| [zeiss-smartzoom](equipment/zeiss/zeiss-smartzoom.json) | 계열 | optical_microscope | microscopy | – | – | magnification=1.6–2021; tilt_angle_deg=-45–45; working_distance_mm=10–330; field_of_view_mm=1.9–353 | limited |
| [zeiss-spectrum](equipment/zeiss/zeiss-spectrum.json) | 계열 | coordinate_measuring_machine |  | – | – | measuring_range_x_mm=700–900; measuring_range_y_mm=700–1800; measuring_range_z_mm=600 | limited |
| [zeiss-stemi-508](equipment/zeiss/zeiss-stemi-508.json) | 기종 | optical_microscope | microscopy | – | – | zoom_ratio=8; magnification=1.9–250; field_of_view_mm=≤122.7; working_distance_mm=35–287; optical_resolution_lp_mm=≤450 | catalog |
| [zeiss-xradia-versa](equipment/zeiss/zeiss-xradia-versa.json) | 계열 | xray_inspection | xray_void_inspection, crystal_structure_analysis | – | – |  | catalog |

## ZwickRoell (`zwickroell`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [zwickroell-aflow-extrusion-plastometer](equipment/zwickroell/zwickroell-aflow-extrusion-plastometer.json) | 기종 | melt_flow_indexer | melt_flow | – | – | melt_temperature_degC=50–450; melt_load_kg=0.325–50; piston_speed_mm_min=≤2000 | catalog |
| [zwickroell-allroundline](equipment/zwickroell/zwickroell-allroundline.json) | 계열 | universal_testing_machine | tensile, compression, flexure, shear, peel, tear, creep, relaxation | 5–250 | -80–250 (부속) | crosshead_speed_mm_min=5e-05–3000; vertical_test_space_mm=1000–2260; horizontal_test_space_mm=440–1040; data_rate_Hz=≤2000 | catalog |
| [zwickroell-arbm120-rotary-bending](equipment/zwickroell/zwickroell-arbm120-rotary-bending.json) | 기종 | rotating_bending_fatigue | fatigue | – | 200–850 (부속) | bending_moment_Nm=2.5–120; rotation_rpm=500–5000; frequency_Hz=8.3–83.3; specimen_diameter_mm=2–20; grip_span_mm=50–200 | catalog |
| [zwickroell-clip-on-extensometers](equipment/zwickroell/zwickroell-clip-on-extensometers.json) | **센서** | extensometer | tensile, compression | – | -70–250 | gauge_length_mm=10–100; displacement_mm=≤40 | limited |
| [zwickroell-cmu-cross-section-measuring-devices](equipment/zwickroell/zwickroell-cmu-cross-section-measuring-devices.json) | **부속** | accessory | tensile, flexure | – | – | specimen_thickness_mm=≤80 | limited |
| [zwickroell-digiclip-extensometers](equipment/zwickroell/zwickroell-digiclip-extensometers.json) | **센서** | extensometer | tensile, compression | – | – | displacement_mm=≤40; displacement_um=≥0.02 | limited |
| [zwickroell-displacement-transducers](equipment/zwickroell/zwickroell-displacement-transducers.json) | **센서** | extensometer | compression, flexure | – | -70–250 | displacement_mm=≤50 | limited |
| [zwickroell-durascan-g5](equipment/zwickroell/zwickroell-durascan-g5.json) | 계열 | vickers_knoop_hardness | hardness_vickers, hardness_knoop, hardness_brinell | – | – | test_load_gf=0.25–62500; hardness_scales=HV, HK, HBW; specimen_height_mm=≤260; specimen_weight_kg=≤50 | catalog |
| [zwickroell-hc-compact](equipment/zwickroell/zwickroell-hc-compact.json) | 계열 | servohydraulic_fatigue | fatigue, fracture_toughness | – | – (부속) | dynamic_force_kN=10–100; stroke_mm=100, 250 | catalog |
| [zwickroell-hdt-vicat](equipment/zwickroell/zwickroell-hdt-vicat.json) | 계열 | hdt_vicat | hdt, vicat | – | 20–300 | heating_rate_K_h=50, 120; stations=3, 4, 6; displacement_mm=1–15; hdt_span_mm=64, 100, 101.6; specimen_max_mm=HDT 13×15×130, VST 10×6.5×10 | catalog |
| [zwickroell-high-temperature-heating-systems](equipment/zwickroell/zwickroell-high-temperature-heating-systems.json) | **부속** | furnace | tensile, creep, compression, flexure | – | -80–2000 | temperature_fluctuation_degC=≤2 | limited |
| [zwickroell-hit-pendulum](equipment/zwickroell/zwickroell-hit-pendulum.json) | 계열 | pendulum_impact | charpy_impact, izod_impact, tensile_impact | – | – | impact_energy_J=0.5–50; impact_velocity_m_s=2.9, 3.46, 3.8 | catalog |
| [zwickroell-kappa-creep](equipment/zwickroell/zwickroell-kappa-creep.json) | 계열 | creep_tester | creep, relaxation, fatigue, thermomechanical_fatigue, fracture_toughness, tensile, compression, flexure | 50, 100 | -80–2000 (부속) | crosshead_speed_mm_min=1.67e-05–250; crosshead_travel_mm=150, 200; vertical_test_space_mm=1397, 1500; horizontal_test_space_mm=520, 720; heating_rate_K_min=≤150 | catalog |
| [zwickroell-laserxtens](equipment/zwickroell/zwickroell-laserxtens.json) | **센서** | extensometer | tensile, creep, compression | – | -80–2000 | specimen_size_mm=≥1.5 | limited |
| [zwickroell-lightxtens-2-1000](equipment/zwickroell/zwickroell-lightxtens-2-1000.json) | **센서** | extensometer | tensile | – | -40–120 | displacement_mm=≤1000 | limited |
| [zwickroell-longstroke-extensometer](equipment/zwickroell/zwickroell-longstroke-extensometer.json) | **센서** | extensometer | tensile | – | -70–250 | displacement_mm=≤1000 | limited |
| [zwickroell-ltm](equipment/zwickroell/zwickroell-ltm.json) | 계열 | electrodynamic_fatigue | fatigue, tensile, compression, flexure | – | – | dynamic_force_kN=1–10; frequency_Hz=≤120; stroke_mm=60; torque_Nm=≤100; rotation_rpm=≤100 | catalog |
| [zwickroell-makroxtens-ii](equipment/zwickroell/zwickroell-makroxtens-ii.json) | **센서** | extensometer | tensile, compression, flexure, fatigue | – | -70–360 | displacement_mm=≤450 | limited |
| [zwickroell-multixtens-ii-hp](equipment/zwickroell/zwickroell-multixtens-ii-hp.json) | **센서** | extensometer | tensile, compression, flexure, fatigue | – | -70–360 | displacement_mm=≤700 | limited |
| [zwickroell-proline](equipment/zwickroell/zwickroell-proline.json) | 계열 | universal_testing_machine | tensile, compression, flexure, peel, tear | 5–100 | – | crosshead_speed_mm_min=≤1000; vertical_test_space_mm=570–1450; horizontal_test_space_mm=440–640 | limited |
| [zwickroell-servohydraulic-load-frames](equipment/zwickroell/zwickroell-servohydraulic-load-frames.json) | 계열 | servohydraulic_fatigue | fatigue, fracture_toughness | – | ≤1000 (부속) | dynamic_force_kN=10–2500; stroke_mm=100, 150, 250, 400; frame_stiffness_kN_mm=300–2100 | catalog |
| [zwickroell-shore-hardness-testers](equipment/zwickroell/zwickroell-shore-hardness-testers.json) | 계열 | shore_irhd_hardness | hardness_shore | – | – | hardness_scales=Shore A, Shore D, Shore B, Shore C, Shore D0, Shore 0, Shore 00, Shore 000; specimen_thickness_mm=≥6; specimen_diameter_mm=≥35 | catalog |
| [zwickroell-specimen-grips](equipment/zwickroell/zwickroell-specimen-grips.json) | **부속** | grip_fixture | tensile | 0.02–2500 | -70–250 |  | limited |
| [zwickroell-specimen-preparation-devices](equipment/zwickroell/zwickroell-specimen-preparation-devices.json) | **부속** | specimen_preparation | tensile, charpy_impact, izod_impact, tensile_impact | – | – | hardness_shore_a=≤60; specimen_thickness_mm=≤8 | limited |
| [zwickroell-temperature-chamber-360c-allroundline](equipment/zwickroell/zwickroell-temperature-chamber-360c-allroundline.json) | **부속** | environmental_chamber | tensile, compression, flexure | ≤250 | -80–360 | test_room_height_mm=≤900; test_room_width_mm=≤460; test_room_depth_mm=≤740 | limited |
| [zwickroell-temperature-chamber-zwickiline](equipment/zwickroell/zwickroell-temperature-chamber-zwickiline.json) | **부속** | environmental_chamber | tensile, compression, flexure | ≤2.5 | -50–180 | test_room_height_mm=≤350; test_room_width_mm=≤250; test_room_depth_mm=≤250 | limited |
| [zwickroell-temperature-chambers-allroundline](equipment/zwickroell/zwickroell-temperature-chambers-allroundline.json) | **부속** | environmental_chamber | tensile, compression, flexure | – | -80–250 | heating_rate_K_min=7.5–13 | catalog |
| [zwickroell-testcontrol-ii-and-control-cube](equipment/zwickroell/zwickroell-testcontrol-ii-and-control-cube.json) | **부속** | accessory | tensile, compression, flexure, fatigue | – | – | data_rate_Hz=≤10000; digital_sample_rate_Hz=≤400000 | limited |
| [zwickroell-testxpert-software](equipment/zwickroell/zwickroell-testxpert-software.json) | software | accessory |  | – | – |  | limited |
| [zwickroell-vibrophore](equipment/zwickroell/zwickroell-vibrophore.json) | 계열 | resonance_fatigue | fatigue, fracture_toughness, tensile, compression, flexure, torsion | – | – | dynamic_force_kN=15–1000; frequency_Hz=30–285; crosshead_speed_mm_min=0.0001–600; vertical_test_space_mm=≤2310; horizontal_test_space_mm=626, 982 | catalog |
| [zwickroell-vibrophore-web](equipment/zwickroell/zwickroell-vibrophore-web.json) | 계열 (보탬→zwickroell-vibrophore) | resonance_fatigue | fatigue, fracture_toughness, tensile, compression | – | – |  | catalog |
| [zwickroell-videoxtens](equipment/zwickroell/zwickroell-videoxtens.json) | **센서** | extensometer | tensile, compression, flexure | – | – |  | limited |
| [zwickroell-xforce-load-cells](equipment/zwickroell/zwickroell-xforce-load-cells.json) | **센서** | load_cell | tensile, compression, flexure, fatigue, torsion | – | – | force_N=5–2500000; dynamic_force_kN=1–1000 | limited |
| [zwickroell-zhr-rockwell](equipment/zwickroell/zwickroell-zhr-rockwell.json) | 계열 | rockwell_hardness | hardness_rockwell, hardness_brinell, hardness_vickers | – | – | test_load_kgf=6.25–250; hardness_scales=HRA–HRV, HR15/30/45 N/T/W/X/Y, HRα plastics E/L/M/R, HR2.5 ball, HBT, HVT 10–100, ball indentation 49–961 N; specimen_he | catalog |
| [zwickroell-zhu250](equipment/zwickroell/zwickroell-zhu250.json) | 기종 | universal_hardness | hardness_vickers, hardness_knoop, hardness_brinell, hardness_rockwell | – | – | test_load_kgf=1–250; hardness_scales=HV1–HV100, HVT, HK1, HBW 1/1 – 10/250, HBT, HRA/B/C/D/E/F/G/H/K, HR15/30/45 N/T, ball indentation 49–961 N; specimen_height | catalog |
| [zwickroell-zwickiline](equipment/zwickroell/zwickroell-zwickiline.json) | 계열 | universal_testing_machine | tensile, compression, flexure | 0.5–5 | -70–360 (부속) | crosshead_speed_mm_min=0.0005–3000 | catalog |

## Zygo (AMETEK) (`zygo`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [zygo-newview-nx2](equipment/zygo/zygo-newview-nx2.json) | 기종 | optical_profilometer | surface_topography | – | – |  | catalog |
