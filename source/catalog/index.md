# 장비 카탈로그 색인

장비 객체 194 개 · 제조사 78 · 노드 1474 · 엣지 2867

`limits` 는 시리즈 전체 범위. 단위는 키 이름에 있다(kN, mm/min, degC …). 빈 칸은 미기재.

## AMETEK / Lloyd Instruments (`ametek-lloyd`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [ametek-lloyd-ls-series](equipment/ametek-lloyd/ametek-lloyd-ls-series.json) | 계열 | universal_testing_machine | tensile, compression, flexure, peel, tear, friction_coefficient, seal_strength | 0.005–5 | – | crosshead_speed_mm_min=0.01–2032; crosshead_travel_mm=500–1400; data_rate_Hz=≤1000 | catalog |

## Anton Paar (`anton-paar`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [anton-paar-mcr-rheometer](equipment/anton-paar/anton-paar-mcr-rheometer.json) | 계열 | rotational_rheometer | rheology_rotational, dma, friction_wear_tribo, tensile, compression, flexure | – | -170–1730 (부속) | torque_mNm=2e-07–300; rotation_rpm=≤6000; frequency_Hz=–; humidity_pct=5–95; viscosity_Pa_s=0.001–100000000 | limited |
| [anton-paar-nanoindentation](equipment/anton-paar/anton-paar-nanoindentation.json) | 계열 | instrumented_indentation | instrumented_indentation, friction_wear_tribo | – | ≤800 | indentation_force_mN=0.1–500 | limited |
| [anton-paar-tribometers](equipment/anton-paar/anton-paar-tribometers.json) | 계열 | tribometer | friction_wear_tribo | – | -160–1000 | force_N=5e-06–70; humidity_pct=5–95; rotation_rpm=1e-06–3000; sliding_speed_m_s=1e-08–3.3; frequency_Hz=0.01–10; torque_mNm=≤450 | catalog |

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

## Audio Precision (`audio-precision`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [audio-precision-apx555](equipment/audio-precision/audio-precision-apx555.json) | 기종 | audio_analyzer | audio_performance | – | – | bandwidth_Hz=≤1000000; residual_thd_n_dB=≤-120; analog_output_voltage_Vrms=≤26; digital_sample_rate_Hz=≤432000; channels=2 | catalog |

## Bareiss (`bareiss`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [bareiss-digi-test-ii](equipment/bareiss/bareiss-digi-test-ii.json) | 기종 | shore_irhd_hardness | hardness_shore, hardness_irhd | – | – | hardness_scales=Shore A, Micro Shore A, Shore A0, Shore B, Shore 0, Shore C, Shore D, Micro Shore D; specimen_thickness_mm=0.5–6 | catalog |

## Brüel & Kjær (HBK) (`bruel-kjaer`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [bruel-kjaer-hats-5128](equipment/bruel-kjaer/bruel-kjaer-hats-5128.json) | 계열 | head_torso_simulator | audio_performance | – | – | frequency_Hz=20–20000; ear_simulators=1, 2 | catalog |

## Bruker (Hysitron) (`bruker`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [bruker-contourx-200](equipment/bruker/bruker-contourx-200.json) | 기종 | optical_profilometer | surface_topography | – | – | scan_range_mm=≤10; vertical_resolution_nm=≤0.01; sample_thickness_mm=≤100; stage_size_mm=≤150; repeatability_pct=≤0.1 | catalog |
| [bruker-dektakxt](equipment/bruker/bruker-dektakxt.json) | 기종 | optical_profilometer | surface_topography, coating_thickness | – | – | scan_length_mm=≤55; vertical_range_mm=≤1; stylus_force_mg=0.03–15; sample_thickness_mm=≤50; stylus_radius_um=2 | limited |
| [bruker-hysitron-pi-95-picoindenter](equipment/bruker/bruker-hysitron-pi-95-picoindenter.json) | 계열 | nanoindenter | instrumented_indentation, compression | – | – | force_N=≤0.0015; displacement_um=≤5; frequency_Hz=110–1800 | catalog |
| [bruker-hysitron-ti-950-triboindenter](equipment/bruker/bruker-hysitron-ti-950-triboindenter.json) | 계열 | nanoindenter | instrumented_indentation, friction_wear_tribo, surface_topography | – | – | indentation_force_mN=–; position_resolution_nm=≤0.02; stage_travel_mm=≤250; data_rate_Hz=≤30000; field_of_view_mm=0.028–0.625; magnification=10–220 | catalog |
| [bruker-hysitron-ts-75-triboscope](equipment/bruker/bruker-hysitron-ts-75-triboscope.json) | **부속** | nanoindenter | instrumented_indentation, surface_topography, friction_wear_tribo | – | – | position_resolution_nm=≤0.0004; indentation_force_mN=– | catalog |

## Buehler (Wilson) (`buehler`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [buehler-wilson-hardness](equipment/buehler/buehler-wilson-hardness.json) | 계열 | hardness | hardness_rockwell, hardness_vickers, hardness_brinell, hardness_knoop | – | – | test_load_kgf=– | limited |
| [buehler-wilson-uh4000](equipment/buehler/buehler-wilson-uh4000.json) | 계열 | universal_hardness | hardness_brinell, hardness_vickers, hardness_rockwell, hardness_knoop | – | – | test_load_kgf=0.5–750; hardness_scales=HV 0.5 – HV 100, HBW 1/1 – HBW 10/3000 (UH4750: HBW 10/750 max), HRA–HRV, HR15/30/45 N/T, HK, ball indentation (plastics) | catalog |
| [buehler-wilson-vh3300](equipment/buehler/buehler-wilson-vh3300.json) | 계열 | vickers_knoop_hardness | hardness_vickers, hardness_knoop | – | – | test_load_gf=10–50000; hardness_scales=HV, HK; specimen_height_mm=≤215; stage_travel_mm=180×180, 300×180 | catalog |

## Chroma ATE (`chroma`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [chroma-17011-battery-cell-tester](equipment/chroma/chroma-17011-battery-cell-tester.json) | 계열 | battery_cycler | battery_cycle_life | – | – | voltage_V=0–6; current_A=≤1200; current_response_time_us=≤100 | catalog |
| [chroma-19032-safety-analyzer](equipment/chroma/chroma-19032-safety-analyzer.json) | 계열 | hipot_safety_analyzer | dielectric_withstand, insulation_resistance, ground_bond | – | – | ac_withstand_voltage_kV=0.05–5.0; dc_withstand_voltage_kV=0.05–6.0; cutoff_current_A=≤0.1; insulation_test_voltage_kV=0.05–3.0; insulation_resistance_ohm=100000 | catalog |
| [chroma-61500-ac-source](equipment/chroma/chroma-61500-ac-source.json) | 계열 | ac_power_source | power_consumption, surge_eft_immunity | – | – | output_power_VA=500–4000; output_voltage_V=0–300; crest_factor=≤6; harmonic_order=≤40; phases=1, 3 | catalog |
| [chroma-63200-dc-load](equipment/chroma/chroma-63200-dc-load.json) | 계열 | electronic_load | power_consumption, battery_cycle_life | – | – | voltage_V=0–1000; current_A=0–1000; power_W=260–15600; dynamic_frequency_Hz=≤20000; slew_rate_A_us=≤41.6; min_rise_time_us=20–150 | catalog |

## C.S.C. Force Measurement (`cscforce`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [cscforce-wt-205m](equipment/cscforce/cscforce-wt-205m.json) | 기종 | crimp_pull_tester | crimp_pull_strength | – | – | pull_force_N=≤1000; wire_diameter_mm=≤6.3 | catalog |

## Cincinnati Sub-Zero (CSZ) (`csz`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [csz-z-plus-chambers](equipment/csz/csz-z-plus-chambers.json) | 계열 | climatic_chamber | damp_heat, temperature_cycling | – | – | chamber_volume_L=227–2718 | limited |

## Daekyung Tech (대경테크) (`daekyung-tech`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [daekyung-tech-dtb-brinell](equipment/daekyung-tech/daekyung-tech-dtb-brinell.json) | 계열 | brinell_hardness | hardness_brinell | – | – | test_load_kgf=500, 750, 1000, 1500, 2000, 2500, 3000; specimen_height_mm=≤175; hardness_scales=HBW; weight_kg=≤135 | limited |

## DeFelsko (`defelsko`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [defelsko-positest-pt](equipment/defelsko/defelsko-positest-pt.json) | 기종 | scratch_hardness_tester | scratch_pencil_hardness | – | – | pencil_hardness_grade=– | limited |

## EMCO-TEST (`emco-test`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [emco-test-durajet-g5](equipment/emco-test/emco-test-durajet-g5.json) | 계열 | rockwell_hardness | hardness_rockwell, hardness_vickers, hardness_brinell | – | – | test_load_kgf=1–250; hardness_scales=HRA–HRV, HR15/30/45 N/T/W/X/Y, HR 2/10, 2/20, 2/120, HVT 5–100, HBT 1/5 – 2.5/187.5, 5/250, plastics 49–961 N; specimen_hei | catalog |
| [emco-test-duravision-g5](equipment/emco-test/emco-test-duravision-g5.json) | 계열 | universal_hardness | hardness_brinell, hardness_vickers, hardness_rockwell, hardness_knoop | – | – | test_load_kgf=0.3–3000; hardness_scales=HBW 1/1 – 10/3000, HV 0.3 – HV 150, HK 0.3 – HK 2, HRA–HRV, HR15/30/45 N/T/W/X/Y, plastics 49–961 N, carbon DIN 51917; s | catalog |

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
| [espec-platinous-chambers](equipment/espec/espec-platinous-chambers.json) | 계열 | climatic_chamber | damp_heat, temperature_cycling | – | -70–200 | humidity_pct=5–98; heating_rate_K_min=3–6; cooling_rate_K_min=1–5; chamber_volume_L=225–900 | catalog |
| [espec-qualmark-halt-hass](equipment/espec/espec-qualmark-halt-hass.json) | 계열 | halt_hass_chamber | halt_hass, vibration_sine_random, temperature_cycling, thermal_shock | – | -100–250 | heating_rate_K_min=≤70; acceleration_gRMS=5–75; table_size_mm=457–2794; payload_kg=45–907 | catalog |
| [espec-tsa-thermal-shock](equipment/espec/espec-tsa-thermal-shock.json) | 계열 | thermal_shock_chamber | thermal_shock, temperature_cycling | – | -70–200 | preheat_limit_degC=≤205; precool_limit_degC=≥-77; temperature_fluctuation_degC=≤0.5; chamber_volume_L=40.8–299.2; load_kg=30–50; ambient_degC=0–40 | catalog |
| [espec-walk-in-chambers](equipment/espec/espec-walk-in-chambers.json) | 계열 | climatic_chamber | damp_heat, temperature_cycling | – | -70–150 | humidity_pct=10–95; heating_rate_K_min=1–4; cooling_rate_K_min=0.4–3 | catalog |

## ETS-Lindgren (`ets-lindgren`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [ets-lindgren-shielding](equipment/ets-lindgren/ets-lindgren-shielding.json) | 계열 | shielded_enclosure | shielding_effectiveness, emi_emission | – | – | frequency_Hz=14000–1000000000; insertion_gain=– | limited |
| [ets-lindgren-smart-reverberation-chamber](equipment/ets-lindgren/ets-lindgren-smart-reverberation-chamber.json) | 계열 | reverberation_chamber | emi_emission, shielding_effectiveness, esd_immunity, surge_eft_immunity | – | – | frequency_Hz=80000000–40000000000; chamber_volume_L=– | limited |

## Teledyne FLIR (`flir`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [flir-t660](equipment/flir/flir-t660.json) | 기종 | thermal_imager | thermography | – | ≤2000 | ir_resolution_pixels=≤307200; thermal_sensitivity_degC=≤0.04 | catalog |
| [flir-t800-series](equipment/flir/flir-t800-series.json) | 계열 | thermal_imager | thermography | – | -40–2000 | ir_resolution_pixels=≤307200; accuracy_degC=– | catalog |

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

## Hegewald & Peschke (`hegewald-peschke`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [hegewald-peschke-at130-hardness](equipment/hegewald-peschke/hegewald-peschke-at130-hardness.json) | 계열 | rockwell_hardness | hardness_rockwell, hardness_brinell, hardness_vickers | – | – | load_N=29.4–1839; hardness_scales=HRA, HRB, HRC, HRD, HRF, HRG, HB/30, HRN 전 스케일 | catalog |
| [hegewald-peschke-bending-fatigue-wire](equipment/hegewald-peschke/hegewald-peschke-bending-fatigue-wire.json) | 계열 | mechanical_dynamic | fatigue, flexure | – | – | wire_diameter_mm=0.3–10; rotation_deg=≤180; stations=≤3; power_kW=≤4.0; weight_kg=300 | catalog |
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
| [hegewald-peschke-pendulum-impact](equipment/hegewald-peschke/hegewald-peschke-pendulum-impact.json) | 계열 | pendulum_impact | charpy_impact, izod_impact, tensile_impact | – | – | impact_energy_J=0.75–750; impact_velocity_m_s=0.39–5.5; data_rate_Hz=≤10000000 | catalog |
| [hegewald-peschke-rim-hardness-line](equipment/hegewald-peschke/hegewald-peschke-rim-hardness-line.json) | 계열 | brinell_hardness | hardness_brinell | 3.5 | – | test_time_s=30–60 | limited |
| [hegewald-peschke-rotational-impact-tester](equipment/hegewald-peschke/hegewald-peschke-rotational-impact-tester.json) | 계열 | high_speed_tensile | high_speed_tensile, tensile_impact | 0.1–80 | – | impact_velocity_m_s=1–14; impact_energy_J=≤16300; displacement_mm=≤3.6; data_rate_Hz=≤400000 | catalog |
| [hegewald-peschke-temperature-chambers](equipment/hegewald-peschke/hegewald-peschke-temperature-chambers.json) | **부속** | environmental_chamber | tensile, compression, flexure | – | -80–260 | heating_rate_K_min=≤10; cooling_rate_K_min=≤8; accuracy_degC=0.5–2; power_VA=2500–11500; weight_kg=80–300 | catalog |
| [hegewald-peschke-torsion](equipment/hegewald-peschke/hegewald-peschke-torsion.json) | 계열 | torsion_tester | torsion, fatigue | – | – | torque_Nm=200–5000; rotation_rpm=0.005–60; rotation_deg=–; specimen_diameter_mm=0.5–350; weight_kg=105–750 | catalog |

## Helmut Fischer (`helmut-fischer`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [helmut-fischer-fischerscope-xray](equipment/helmut-fischer/helmut-fischer-fischerscope-xray.json) | 계열 | xrf_thickness | coating_thickness | – | – | coating_thickness_um=–; element_count=≤24; measurement_spot_um=≥20 | catalog |

## HIOKI (`hioki`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [hioki-st5520-insulation-tester](equipment/hioki/hioki-st5520-insulation-tester.json) | 기종 | insulation_tester | insulation_resistance | – | – | insulation_test_voltage_V=25–1000; insulation_resistance_ohm=0–4000000000; response_time_ms=≤20 | catalog |

## Hirayama Manufacturing (`hirayama`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [hirayama-hast-pc-r9](equipment/hirayama/hirayama-hast-pc-r9.json) | 계열 | hast_chamber | hast, damp_heat | – | 105–162.5 | humidity_pct=65–100; chamber_volume_L=26–84.4; pressure_MPa=0.019–0.393 | limited |

## Hitachi High-Tech Analytical Science (`hitachi-high-tech`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [hitachi-nexta-sta](equipment/hitachi-high-tech/hitachi-nexta-sta.json) | 계열 | sta | tga, dsc | – | 20–1500 | balance_resolution_ug=– | catalog |

## Hot Disk AB (`hot-disk`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [hot-disk-tps-2500-s](equipment/hot-disk/hot-disk-tps-2500-s.json) | 기종 | thermal_conductivity | thermal_conductivity | – | -253–1000 | thermal_conductivity_W_mK=0.005–1800; thermal_diffusivity_mm2_s=0.01–1400; specimen_thickness_mm=≥0.01; measurement_time_s=1–2560 | catalog |

## IMV Corporation (`imv`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [imv-i-series-shaker](equipment/imv/imv-i-series-shaker.json) | 계열 | vibration_shaker | vibration_sine_random, mechanical_shock | 8–65 | – | frequency_Hz=0–3300; displacement_mm=≤100; velocity_m_s=≤4.6; payload_kg=– | catalog |

## INFICON (`inficon`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [inficon-leak-detectors](equipment/inficon/inficon-leak-detectors.json) | 계열 | helium_leak_detector | leak_rate | – | – | leak_rate_mbar_L_s=≥5e-12; helium_pumping_speed_L_s=≤36 | catalog |

## INNOVATEST (`innovatest`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [innovatest-nexus-3200](equipment/innovatest/innovatest-nexus-3200.json) | 기종 | brinell_hardness | hardness_brinell | – | – | test_load_kgf=62.5–3000; hardness_scales=HBW 2.5/62.5, HBW 2.5/187.5, HBW 5/62.5, HBW 5/125, HBW 5/250, HBW 5/750, HBW 10/100, HBW 10/125; specimen_height_mm=≤2 | catalog |

## Instron (`instron`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [instron-3119-160-furnace](equipment/instron/instron-3119-160-furnace.json) | **부속** | furnace | tensile, creep, fatigue | – | 200–1050 | heated_length_mm=300; bore_diameter_mm=75 | catalog |
| [instron-3119-600-environmental-chambers](equipment/instron/instron-3119-600-environmental-chambers.json) | **부속** | environmental_chamber | tensile, compression, flexure, fatigue | – | -150–600 |  | catalog |
| [instron-3400-series](equipment/instron/instron-3400-series.json) | 계열 | universal_testing_machine | tensile, compression, flexure, peel, puncture, friction_coefficient, shear, tear | 0.5–300 | – | crosshead_speed_mm_min=5e-05–1016; vertical_test_space_mm=651–1744; horizontal_test_space_mm=100–575; data_rate_Hz=≤1000 | catalog |
| [instron-5900-series](equipment/instron/instron-5900-series.json) | 계열 | universal_testing_machine | tensile, compression, flexure, shear, peel, tear, fatigue, creep | 0.5–600 | – | crosshead_speed_mm_min=0.0001–3000; vertical_test_space_mm=726–2050; horizontal_test_space_mm=100–763; data_rate_Hz=≤2500 | catalog |
| [instron-6800-series](equipment/instron/instron-6800-series.json) | 계열 | universal_testing_machine | tensile, compression, flexure, peel, puncture, friction_coefficient, shear, tear, creep, relaxation | 0.5–300 | -150–1200 (부속) | crosshead_speed_mm_min=5e-05–3048; vertical_test_space_mm=738–1993; horizontal_test_space_mm=100–947; data_rate_Hz=≤5000 | catalog |
| [instron-8800-servohydraulic](equipment/instron/instron-8800-servohydraulic.json) | 계열 | servohydraulic_fatigue | fatigue, fracture_toughness, tensile, compression, flexure, torsion, high_speed_tensile | – | – | dynamic_force_kN=25–250; torque_Nm=100; stroke_mm=100; frequency_Hz=–; vertical_test_space_mm=≤1067 | catalog |
| [instron-9400-drop-tower](equipment/instron/instron-9400-drop-tower.json) | 계열 | drop_tower_impact | drop_weight_impact, puncture, tensile_impact | 0.45–222 | – | impact_energy_J=0.15–1800; impact_velocity_m_s=0.77–24; drop_height_m=0.03–29.4; drop_mass_kg=0.5–70 | catalog |
| [instron-ave-video-extensometer](equipment/instron/instron-ave-video-extensometer.json) | **센서** | extensometer | tensile, compression, flexure | – | – | field_of_view_mm=85–840; gauge_length_mm=≥2.5; data_rate_Hz=≤500; following_speed_mm_min=≤2500 | catalog |
| [instron-ceast-9050-pendulum](equipment/instron/instron-ceast-9050-pendulum.json) | 계열 | pendulum_impact | charpy_impact, izod_impact, tensile_impact | – | – | impact_energy_J=0.5–50; impact_velocity_m_s=1–3.8; specimen_diameter_mm=≤25 | catalog |
| [instron-ceast-melt-flow-mf](equipment/instron/instron-ceast-melt-flow-mf.json) | 계열 | melt_flow_indexer | melt_flow | – | – | melt_temperature_degC=30–400; melt_load_kg=0.325–21.6 | catalog |
| [instron-electropuls-e3000](equipment/instron/instron-electropuls-e3000.json) | 기종 | electrodynamic_fatigue | fatigue, tensile, compression, flexure, torsion, dma | – | – | dynamic_force_kN=≤3; static_force_kN=≤2.1; torque_Nm=≤25; stroke_mm=60; rotation_deg=≤135; frequency_Hz=≤100; vertical_test_space_mm=≤861; horizontal_test_space | catalog |
| [instron-hv-series-hdt-vicat](equipment/instron/instron-hv-series-hdt-vicat.json) | 계열 | hdt_vicat | hdt, vicat | – | 20–500 | stations=3, 6; heating_rate_K_h=50, 120 | catalog |
| [instron-mt-microtorsion](equipment/instron/instron-mt-microtorsion.json) | 계열 | torsion_tester | torsion | – | – | torque_Nm=0.225–225; rotation_rpm=0.01–120; rotation_deg=≤5400000; specimen_diameter_mm=≤203; test_opening_mm=381–775 | catalog |

## Instrument Systems (`instrument-systems`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [instrument-systems-lumicam-4000b](equipment/instrument-systems/instrument-systems-lumicam-4000b.json) | 계열 | imaging_colorimeter | photometry_colorimetry | – | – | luminance_cd_m2=0.0003–4300000; resolution_pixels=≤12288000; dynamic_range=≤43000000000 | catalog |

## Keysight Technologies (`keysight`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [keysight-n9048b-pxe](equipment/keysight/keysight-n9048b-pxe.json) | 계열 | emi_receiver | emi_emission | – | – | frequency_Hz=1–44000000000; resolution_bandwidth_Hz=10–1000000 | catalog |

## KIC Thermal (`kic`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [kic-sra-reflow-analyzer](equipment/kic/kic-sra-reflow-analyzer.json) | 기종 | thermal_profiler | thermal_profiling, solderability | – | – | profile_storage=≤30 | limited |

## Kikusui Electronics (`kikusui`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [kikusui-tos9300](equipment/kikusui/kikusui-tos9300.json) | 계열 | hipot_safety_analyzer | dielectric_withstand, insulation_resistance, ground_bond | – | – | ac_withstand_voltage_kV=≤5.0; dc_withstand_voltage_kV=≤7.2; insulation_resistance_ohm=1000–100000000000; leakage_current_A=1e-06–0.1; ground_bond_resistance_ohm | catalog |

## KLA Instruments (Nanomechanics) (`kla`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [kla-imicro](equipment/kla/kla-imicro.json) | 기종 | instrumented_indentation | instrumented_indentation, friction_wear_tribo, dma | – | ≤300 | indentation_force_mN=≤1000; data_rate_Hz=≤100000 | catalog |

## Konica Minolta Sensing (`konica-minolta`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [konica-minolta-ca-410](equipment/konica-minolta/konica-minolta-ca-410.json) | 계열 | display_color_analyzer | photometry_colorimetry | – | – | luminance_cd_m2=0.002–12000; acceptance_angle_deg=4–10; measurement_distance_mm=28–200 | catalog |
| [konica-minolta-cs-2000](equipment/konica-minolta/konica-minolta-cs-2000.json) | 계열 | spectroradiometer | photometry_colorimetry | – | – | luminance_cd_m2=0.0005–50000000; illuminance_lx=1.0–7500000; spectral_bandwidth_nm=≤5; measuring_angle_deg=1, 0.2, 0.1; polarization_error_pct=≤2 | catalog |

## Lansmont Corporation (`lansmont`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [lansmont-pdt-drop-testers](equipment/lansmont/lansmont-pdt-drop-testers.json) | 계열 | drop_tester | free_fall_drop | – | – | payload_kg=≤80; drop_height_mm=25–1830; package_size_mm=≤915 | catalog |
| [lansmont-shock-test-systems](equipment/lansmont/lansmont-shock-test-systems.json) | 계열 | shock_test_machine | mechanical_shock, free_fall_drop | – | – | acceleration_g=1000–10000; pulse_duration_ms=≥0.25; velocity_change_m_s=6.1–18; payload_kg=50–1134; table_size_mm=230–1220 | catalog |

## QMESYS (큐머시스) (`limotem`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [qmesys-qm100](equipment/limotem/qmesys-qm100.json) | 계열 | universal_testing_machine | tensile, compression, flexure, peel, tear, friction_coefficient, shear | 0.049–294 | – | crosshead_speed_mm_min=0.1–600; crosshead_travel_mm=450–1100; horizontal_test_space_mm=350–660 | catalog |

## LINSEIS (`linseis`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [linseis-thermal-conductivity](equipment/linseis/linseis-thermal-conductivity.json) | 계열 | thermal_conductivity | thermal_conductivity | – | -170–2800 | thermal_diffusivity_mm2_s=0.01–1000; thermal_conductivity_W_mK=0.1–2000; heating_rate_K_min=≤300 | catalog |
| [linseis-tma-l71-l72](equipment/linseis/linseis-tma-l71-l72.json) | 계열 | tma | tma, dma, creep, relaxation, dilatometry | – | -180–2400 | force_N=0.001–20; frequency_Hz=0.01–50; heating_rate_K_min=0.1–100; sample_length_mm=20–50; specimen_diameter_mm=≤10 | catalog |

## Maccor (`maccor`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [maccor-series-4000](equipment/maccor/maccor-series-4000.json) | 계열 | battery_cycler | battery_cycle_life | – | – | voltage_V=-2–8; current_A=0.00015–20; channels=–; fra_frequency_Hz=≥0.001; fra_current_A=≤3.0; fra_voltage_V=≤55 | catalog |

## Malvern Panalytical (`malvern-panalytical`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [malvern-kinexus](equipment/malvern-panalytical/malvern-kinexus.json) | 계열 | rotational_rheometer | rheology_rotational | – | -40–200 | torque_mNm=5e-07–250; angular_velocity_rad_s=1e-08–500; frequency_Hz=1e-06–150; force_N=0.001–50 | catalog |

## Mecmesin (`mecmesin`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [mecmesin-multitest](equipment/mecmesin/mecmesin-multitest.json) | 계열 | force_tester | tensile, compression, peel, flexure, friction_coefficient | 0.002–50 | – | crosshead_speed_mm_min=0.1–1200; crosshead_travel_mm=500–1200 | catalog |
| [mecmesin-omnitest](equipment/mecmesin/mecmesin-omnitest.json) | 계열 | universal_testing_machine | tensile, compression, flexure, shear, peel, tear, friction_coefficient | 0.002–50 | – | crosshead_speed_mm_min=0.01–500; crosshead_travel_mm=507–1230; horizontal_test_space_mm=420, 425; data_rate_Hz=≤1000 | catalog |

## METTLER TOLEDO (`mettler-toledo`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [mettler-dma-sdta861e](equipment/mettler-toledo/mettler-dma-sdta861e.json) | 기종 | dma | dma | – | -150–500 | force_N=0.001–40; frequency_Hz=0.001–1000; displacement_um=≤1600; sample_length_mm=≤100 | catalog |
| [mettler-tga-dsc-1](equipment/mettler-toledo/mettler-tga-dsc-1.json) | 계열 | sta | tga, dsc | – | 20–1600 | heating_rate_K_min=≤250; sample_mass_mg=≤5000; balance_resolution_ug=≥0.1; sample_volume_uL=≤900 | catalog |

## Mitutoyo (`mitutoyo`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [mitutoyo-hardmatic-ud-410-leeb](equipment/mitutoyo/mitutoyo-hardmatic-ud-410-leeb.json) | 계열 | portable_hardness | hardness_leeb | – | – | hardness_scales=HLD, HLDC, HLD+15, HLDL | limited |
| [mitutoyo-hm-micro-vickers](equipment/mitutoyo/mitutoyo-hm-micro-vickers.json) | 계열 | vickers_knoop_hardness | hardness_vickers, hardness_knoop | – | – | test_load_gf=0.05–2000; hardness_scales=HV, HK; specimen_height_mm=≤133; specimen_depth_mm=≤160 | catalog |
| [mitutoyo-hr-series-rockwell](equipment/mitutoyo/mitutoyo-hr-series-rockwell.json) | 계열 | rockwell_hardness | hardness_rockwell, hardness_brinell | – | – | test_load_kgf=6.25–187.5; hardness_scales=HRA, HRB, HRC, HRD, HRE, HRF, HRG, HRH; specimen_height_mm=≤395; specimen_depth_mm=≤165 | catalog |

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
| [mts-acumen](equipment/mts/mts-acumen.json) | 계열 | electrodynamic_fatigue | fatigue, tensile, compression, flexure, torsion, dma | – | – | dynamic_force_kN=1.25–12; static_force_kN=1–8.5; torque_Nm=30, 120; stroke_mm=70; rotation_deg=≤135; frequency_Hz=≤100; vertical_test_space_mm=0–985; horizontal | catalog |
| [mts-bionix-tabletop](equipment/mts/mts-bionix-tabletop.json) | 계열 | servohydraulic_fatigue | fatigue, tensile, compression, torsion, flexure | – | – | dynamic_force_kN=15, 25; torque_Nm=150, 250; stroke_mm=100, 150; rotation_deg=≤135; vertical_test_space_mm=30–1335; horizontal_test_space_mm=460 | catalog |
| [mts-criterion-series-40](equipment/mts/mts-criterion-series-40.json) | 계열 | universal_testing_machine | tensile, compression, flexure, shear, peel, tear | 0.001–1200 | – | crosshead_speed_mm_min=0.005–3000; vertical_test_space_mm=820–2000; horizontal_test_space_mm=100–1000; data_rate_Hz=≤5000 | catalog |
| [mts-exceed-series-40](equipment/mts/mts-exceed-series-40.json) | 계열 | universal_testing_machine | tensile, compression, flexure, shear, peel | 0.005–600 | – | crosshead_speed_mm_min=0.001–508; vertical_test_space_mm=700–1450; horizontal_test_space_mm=100–750; data_rate_Hz=≤2500 | catalog |
| [mts-landmark-servohydraulic](equipment/mts/mts-landmark-servohydraulic.json) | 계열 | servohydraulic_fatigue | fatigue, fracture_toughness, thermomechanical_fatigue, tensile, compression, flexure, relaxation | – | – | dynamic_force_kN=5–500; stroke_mm=100, 150, 250; frequency_Hz=≤200; vertical_test_space_mm=0–2129; horizontal_test_space_mm=460, 533, 635, 762 | catalog |

## NETZSCH Analyzing & Testing (`netzsch`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [netzsch-arc-244-305](equipment/netzsch/netzsch-arc-244-305.json) | 계열 | accelerating_rate_calorimeter | thermal_runaway_calorimetry, battery_abuse | – | 20–500 | pressure_bar=0–150; sample_volume_mL=0.5–130; tracking_rate_K_min=≤200; temperature_reproducibility_K=≤0.1 | catalog |
| [netzsch-dil-402-expedis](equipment/netzsch/netzsch-dil-402-expedis.json) | 계열 | dilatometer | dilatometry, tma | – | -180–2800 | heating_rate_K_min=0.001–100; displacement_um=≤25000; force_N=0.01–3; sample_length_mm=≤52; specimen_diameter_mm=≤19 | catalog |
| [netzsch-dsc-300-caliris](equipment/netzsch/netzsch-dsc-300-caliris.json) | 계열 | dsc | dsc | – | -180–750 | heating_rate_K_min=≤500; sample_mass_mg=– | catalog |
| [netzsch-lfa-467-hyperflash](equipment/netzsch/netzsch-lfa-467-hyperflash.json) | 계열 | thermal_conductivity | thermal_conductivity | – | -100–1250 | heating_rate_K_min=≤50; thermal_diffusivity_mm2_s=0.01–2000; thermal_conductivity_W_mK=0.1–4000; specimen_diameter_mm=≤25.4; specimen_thickness_mm=0.01–6; stati | catalog |
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

## Nikon Metrology (`nikon`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [nikon-xt-h-series](equipment/nikon/nikon-xt-h-series.json) | 계열 | xray_inspection | xray_void_inspection | – | – | tube_voltage_kV=180–225; spot_size_um=≥3 | catalog |

## Noise Laboratory (NOISEKEN) (`noiseken`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [noiseken-ess-s3011a](equipment/noiseken/noiseken-ess-s3011a.json) | 기종 | esd_simulator | esd_immunity | – | – | esd_voltage_kV=0.2–30.0; discharge_mode=contact, air; polarity=positive, negative | catalog |

## Nordson Test & Inspection (DAGE / Sonoscan) (`nordson-dage`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [nordson-dage-4000plus-bondtester](equipment/nordson-dage/nordson-dage-4000plus-bondtester.json) | 기종 | bond_tester | wire_bond_strength | – | – | push_force_kgf=≤50; pull_force_kgf=≤100; shear_force_kgf=≤200; stage_travel_mm=≤300 | catalog |
| [nordson-dage-quadra-xray](equipment/nordson-dage/nordson-dage-quadra-xray.json) | 계열 | xray_inspection | xray_void_inspection | – | – | tube_voltage_kV=30–160; tube_power_W=10–20; feature_recognition_um=≥0.1; magnification=≤68000; inspection_area_mm=≤510; sample_size_mm=≤740; sample_weight_kg=≤5 | catalog |
| [nordson-dage-sonoscan-gen6](equipment/nordson-dage/nordson-dage-sonoscan-gen6.json) | 기종 | acoustic_microscope | acoustic_delamination | – | – | wafer_size_mm=≤300; transducer_frequency_MHz=– | limited |

## PerkinElmer (`perkinelmer`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [perkinelmer-dsc-8000](equipment/perkinelmer/perkinelmer-dsc-8000.json) | 계열 | dsc | dsc | – | – | heating_rate_K_min=0.01–750; pressure_psi=≤600 | limited |

## Proceq (Screening Eagle) (`proceq`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [proceq-equotip-550-leeb](equipment/proceq/proceq-equotip-550-leeb.json) | 기종 | portable_hardness | hardness_leeb | – | – | hardness_scales=HLD, HLDC, HLDL, HLS, HLE, HLG, HLC; impact_energy_Nmm=3, 11, 90; sample_mass_kg=≥0.02 | catalog |

## Q-Lab Corporation (`q-lab`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [q-lab-q-fog](equipment/q-lab/q-lab-q-fog.json) | 계열 | corrosion_chamber | salt_spray_corrosion, damp_heat | – | – | chamber_volume_L=600, 1100; humidity_pct=20–100 | catalog |
| [q-lab-q-sun](equipment/q-lab/q-lab-q-sun.json) | 계열 | weathering_tester | accelerated_weathering | – | – | irradiance_control_nm=340, 420, 300-400 (TUV); humidity_pct=–; stations=17, 31, 55 | catalog |
| [q-lab-quv](equipment/q-lab/q-lab-quv.json) | 기종 | weathering_tester | accelerated_weathering | – | – |  | limited |

## Rohde & Schwarz (`rohde-schwarz`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [rs-esw-emi-receiver](equipment/rohde-schwarz/rs-esw-emi-receiver.json) | 계열 | emi_receiver | emi_emission | – | – | frequency_Hz=2–44000000000; resolution_bandwidth_Hz=≤1000000 | catalog |

## SALT Co. (Light-SALT) (`salt`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [salt-st-1000-series-electromechanical-utm](equipment/salt/salt-st-1000-series-electromechanical-utm.json) | 계열 | universal_testing_machine | tensile, compression, flexure, peel, tear | 3–300 | -100–1200 (부속) | crosshead_speed_mm_min=0.01–2000; vertical_test_space_mm=600–1290; horizontal_test_space_mm=170–620; weight_kg=70–1450 | limited |
| [salt-st-1004-hydraulic-utm](equipment/salt/salt-st-1004-hydraulic-utm.json) | 계열 | hydraulic_utm | tensile, compression, flexure | 300–3000 | – | crosshead_speed_mm_min=0.1–400; stroke_mm=200–750; vertical_test_space_mm=680–1350; specimen_diameter_mm=4–70; specimen_thickness_mm=0–70 | limited |

## Shimadzu (`shimadzu`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [shimadzu-ags-v](equipment/shimadzu/shimadzu-ags-v.json) | 계열 | universal_testing_machine | tensile, compression, flexure, peel, tear, friction_coefficient | 0.001–10 | – | crosshead_speed_mm_min=0.0005–1500; return_speed_mm_min=≤1650; vertical_test_space_mm=≤1180; horizontal_test_space_mm=425; data_rate_Hz=≤5000 | catalog |
| [shimadzu-ags-x](equipment/shimadzu/shimadzu-ags-x.json) | 계열 | universal_testing_machine | tensile, compression, flexure, shear, peel, tear | 0.001–300 | -70–1100 (부속) | crosshead_speed_mm_min=0.001–1600; vertical_test_space_mm=1200–1475; horizontal_test_space_mm=425–600; data_rate_Hz=≤1000; humidity_pct=40–95 | catalog |
| [shimadzu-agx-v2](equipment/shimadzu/shimadzu-agx-v2.json) | 계열 | universal_testing_machine | tensile, compression, flexure, shear, peel, tear, creep, relaxation | 0.01–600 | -70–1100 (부속) | crosshead_speed_mm_min=5e-05–3000; vertical_test_space_mm=180–2325; horizontal_test_space_mm=420–790; frame_stiffness_kN_mm=60–700; data_rate_Hz=≤10000 | catalog |
| [shimadzu-duh-211](equipment/shimadzu/shimadzu-duh-211.json) | 계열 | instrumented_indentation | instrumented_indentation, hardness_vickers, hardness_knoop | – | – | indentation_force_mN=0.1–1961; displacement_um=0–100; specimen_height_mm=≤60; stage_travel_mm=25×25 | catalog |
| [shimadzu-hmv-g](equipment/shimadzu/shimadzu-hmv-g.json) | 계열 | vickers_knoop_hardness | hardness_vickers, hardness_knoop | – | – | test_load_gf=1–2000; hardness_scales=HV, HK | limited |
| [shimadzu-uh-x-fx](equipment/shimadzu/shimadzu-uh-x-fx.json) | 계열 | hydraulic_utm | tensile, compression, flexure | 200–4000 | – | crosshead_speed_mm_min=0.1–100; stroke_mm=200–350; grip_span_mm=720–1150; specimen_diameter_mm=8–120; specimen_thickness_mm=0–120 | catalog |

## Shinyei Testing Machinery (`shinyei`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [shinyei-drop-shock-testers](equipment/shinyei/shinyei-drop-shock-testers.json) | 계열 | drop_tester | free_fall_drop, mechanical_shock | – | – | payload_kg=–; drop_height_mm=– | limited |

## Siemens Digital Industries (Simcenter) (`siemens`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [siemens-t3ster](equipment/siemens/siemens-t3ster.json) | 기종 | thermal_transient_tester | thermal_resistance | – | – | time_resolution_us=≥1; measurement_channels=≤8 | catalog |

## Stable Micro Systems (`stable-micro-systems`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [sms-ta-xt-plus](equipment/stable-micro-systems/sms-ta-xt-plus.json) | 기종 | texture_analyser | texture, compression, tensile, puncture, peel | ≤0.5 | -10–80 | crosshead_speed_mm_min=0.6–2400; crosshead_travel_mm=1–295 | limited |

## Struers (`struers`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [struers-duramin-40](equipment/struers/struers-duramin-40.json) | 계열 | vickers_knoop_hardness | hardness_vickers, hardness_knoop, hardness_brinell | – | – | test_load_gf=1–62500; hardness_scales=HV, HK, HBW | catalog |

## TA Instruments (`ta-instruments`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [ta-electroforce](equipment/ta-instruments/ta-electroforce.json) | 계열 | electrodynamic_fatigue | fatigue, dma, tensile, compression, torsion, flexure | – | -150–600 | force_N=0.002–15000; stroke_mm=5–150; frequency_Hz=1e-05–300; torque_Nm=5.6, 14, 25, 49, 70 | catalog |
| [ta-instruments-discovery-dsc](equipment/ta-instruments/ta-instruments-discovery-dsc.json) | 계열 | dsc | dsc | – | -180–725 | accuracy_degC=≤0.025 | catalog |
| [ta-instruments-discovery-hybrid-rheometer](equipment/ta-instruments/ta-instruments-discovery-hybrid-rheometer.json) | 계열 | rotational_rheometer | rheology_rotational | – | – | torque_mNm=≤200; frequency_Hz=1e-07–100; angular_velocity_rad_s=0–300; force_N=≤50 | catalog |
| [ta-instruments-discovery-light-flash](equipment/ta-instruments/ta-instruments-discovery-light-flash.json) | 계열 | thermal_conductivity | thermal_conductivity | – | ≤1600 | thermal_diffusivity_mm2_s=0.01–1000; thermal_conductivity_W_mK=0.1–2000; specimen_thickness_mm=≤10; specimen_diameter_mm=8, 10, 12.7, 15.9, 25.4 | catalog |
| [ta-instruments-discovery-tga](equipment/ta-instruments/ta-instruments-discovery-tga.json) | 계열 | tga | tga | – | ≤1200 | heating_rate_K_min=0.1–500; cooling_rate_K_min=–; sample_mass_mg=≤750; balance_resolution_ug=≤0.001 | catalog |
| [ta-instruments-dma](equipment/ta-instruments/ta-instruments-dma.json) | 계열 | dma | dma | – | -150–600 | force_N=0.0001–18; frequency_Hz=0.01–200; heating_rate_K_min=0.1–20; cooling_rate_K_min=0.1–10; displacement_um=0.5–10000 | catalog |
| [ta-instruments-rsa-g2](equipment/ta-instruments/ta-instruments-rsa-g2.json) | 계열 | dma | dma | – | -150–600 (부속) | force_N=0.0005–35; frequency_Hz=2e-05–100; heating_rate_K_min=0.1–60; cooling_rate_K_min=0.1–60; displacement_mm=5e-05–1.5 | catalog |
| [ta-instruments-sdt-q600](equipment/ta-instruments/ta-instruments-sdt-q600.json) | 계열 | sta | tga, dsc | – | ≤1500 | heating_rate_K_min=0.1–100; sample_volume_uL=40, 90, 110 | catalog |
| [ta-instruments-vti-sa-sorption](equipment/ta-instruments/ta-instruments-vti-sa-sorption.json) | 계열 | vapor_sorption_analyzer | vapor_sorption, tga | – | 5–150 | humidity_pct=–; sample_mass_mg=≤5000; balance_resolution_ug=≥0.01 | catalog |

## Taber Industries (`taber`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [taber-rotary-abraser-5135-5155](equipment/taber/taber-rotary-abraser-5135-5155.json) | 계열 | abrasion_tester | abrasion | – | – | rotation_rpm=60, 72; load_g=250, 500, 1000; specimen_thickness_mm=≤40; stations=1, 2 | catalog |

## Teseq / AMETEK CTS (`teseq`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [teseq-nsg-3060](equipment/teseq/teseq-nsg-3060.json) | 계열 | transient_generator | surge_eft_immunity | – | – | surge_voltage_kV=0.2–6.6; eft_voltage_kV=0.2–4.8; polarity=positive, negative; cdn_voltage_V=≤480; cdn_current_A=≤100 | catalog |
| [teseq-nsg-438](equipment/teseq/teseq-nsg-438.json) | 기종 | esd_simulator | esd_immunity | – | – | esd_voltage_kV=0.2–30.0; frequency_Hz=0.5–25; discharge_mode=contact, air; polarity=positive, negative, alternating | catalog |

## Testometric (`testometric`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [testometric-m500](equipment/testometric/testometric-m500.json) | 계열 | universal_testing_machine | tensile, compression, flexure, shear, peel, tear, creep, fatigue | 0.005–100 | – | crosshead_speed_mm_min=0.001–1000; vertical_test_space_mm=1180–1300; horizontal_test_space_mm=420; data_rate_Hz=≤12000 | catalog |

## Thermo Fisher Scientific (HAAKE) (`thermo-fisher`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [thermo-haake-mars](equipment/thermo-fisher/thermo-haake-mars.json) | 계열 | rotational_rheometer | rheology_rotational, dma, friction_wear_tribo | – | -150–600 | torque_mNm=2e-06–200; rotation_rpm=1e-08–4500; frequency_Hz=1e-06–100; force_N=0.01–50 | catalog |

## Thermotron Industries (`thermotron`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [thermotron-se-s-series](equipment/thermotron/thermotron-se-s-series.json) | 계열 | climatic_chamber | damp_heat, temperature_cycling | – | – | humidity_pct=10–98 | limited |

## Tinius Olsen (`tinius-olsen`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [tinius-olsen-mp1200-melt-flow](equipment/tinius-olsen/tinius-olsen-mp1200-melt-flow.json) | 계열 | melt_flow_indexer | melt_flow | – | – | melt_temperature_degC=≤450; melt_load_kg=0.325–21.6 | catalog |
| [tinius-olsen-st-series](equipment/tinius-olsen/tinius-olsen-st-series.json) | 계열 | universal_testing_machine | tensile, compression, flexure, shear, tear, peel | 1–300 | – | crosshead_speed_mm_min=0.0001–2500; vertical_test_space_mm=–; data_rate_Hz=≤1000 | catalog |
| [tinius-olsen-torsion-testers](equipment/tinius-olsen/tinius-olsen-torsion-testers.json) | 계열 | torsion_tester | torsion | – | – | torque_Nm=1000–30000; rotation_speed_deg_min=5–360; specimen_diameter_mm=≤127; specimen_length_mm=≤2286 | catalog |

## TIRA GmbH (`tira`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [tira-tiravib-5x-shakers](equipment/tira/tira-tiravib-5x-shakers.json) | 계열 | vibration_shaker | vibration_sine_random | – | – | force_N=40–200; frequency_Hz=2–8000; displacement_mm=≤25; velocity_m_s=≤1.5; acceleration_g=≤102; current_A=≤11.2 | catalog |

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

## Weiss Technik (`weiss-technik`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [weiss-dust-chamber-st](equipment/weiss-technik/weiss-dust-chamber-st.json) | 계열 | dust_chamber | dust_ingress | – | – |  | limited |
| [weiss-shockevent](equipment/weiss-technik/weiss-shockevent.json) | 계열 | thermal_shock_chamber | thermal_shock, temperature_cycling | – | -80–220 |  | catalog |

## Yokogawa Test & Measurement (`yokogawa`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [yokogawa-wt5000](equipment/yokogawa/yokogawa-wt5000.json) | 기종 | power_analyzer | power_consumption | – | – | frequency_Hz=0.1–5000000; current_A=0.005–30; voltage_V=≥1.5; input_elements=≤7; harmonic_order=≤500 | catalog |

## ZwickRoell (`zwickroell`)

| id | 종류 | 분류 | 시험 항목 | 힘 kN | 온도 °C | 기타 한계 | 신뢰도 |
|---|---|---|---|---|---|---|---|
| [zwickroell-aflow-extrusion-plastometer](equipment/zwickroell/zwickroell-aflow-extrusion-plastometer.json) | 기종 | melt_flow_indexer | melt_flow | – | – | melt_temperature_degC=50–450; melt_load_kg=0.325–50; piston_speed_mm_min=≤2000 | catalog |
| [zwickroell-allroundline](equipment/zwickroell/zwickroell-allroundline.json) | 계열 | universal_testing_machine | tensile, compression, flexure, shear, peel, tear, creep, relaxation | 5–250 | -80–250 (부속) | crosshead_speed_mm_min=5e-05–3000; vertical_test_space_mm=1000–2260; horizontal_test_space_mm=440–1040; data_rate_Hz=≤2000 | catalog |
| [zwickroell-arbm120-rotary-bending](equipment/zwickroell/zwickroell-arbm120-rotary-bending.json) | 기종 | rotating_bending_fatigue | fatigue | – | 200–850 (부속) | bending_moment_Nm=2.5–120; rotation_rpm=500–5000; frequency_Hz=8.3–83.3; specimen_diameter_mm=2–20; grip_span_mm=50–200 | catalog |
| [zwickroell-durascan-g5](equipment/zwickroell/zwickroell-durascan-g5.json) | 계열 | vickers_knoop_hardness | hardness_vickers, hardness_knoop, hardness_brinell | – | – | test_load_gf=0.25–62500; hardness_scales=HV, HK, HBW; specimen_height_mm=≤260; specimen_weight_kg=≤50 | catalog |
| [zwickroell-hdt-vicat](equipment/zwickroell/zwickroell-hdt-vicat.json) | 계열 | hdt_vicat | hdt, vicat | – | 20–300 | heating_rate_K_h=50, 120; stations=3, 4, 6; displacement_mm=1–15; hdt_span_mm=64, 100, 101.6; specimen_max_mm=HDT 13×15×130, VST 10×6.5×10 | catalog |
| [zwickroell-hit-pendulum](equipment/zwickroell/zwickroell-hit-pendulum.json) | 계열 | pendulum_impact | charpy_impact, izod_impact, tensile_impact | – | – | impact_energy_J=0.5–50; impact_velocity_m_s=2.9, 3.46, 3.8 | catalog |
| [zwickroell-kappa-creep](equipment/zwickroell/zwickroell-kappa-creep.json) | 계열 | creep_tester | creep, relaxation, fatigue, thermomechanical_fatigue, fracture_toughness, tensile, compression, flexure | 50, 100 | -80–2000 (부속) | crosshead_speed_mm_min=1.67e-05–250; crosshead_travel_mm=150, 200; vertical_test_space_mm=1397, 1500; horizontal_test_space_mm=520, 720; heating_rate_K_min=≤150 | catalog |
| [zwickroell-proline](equipment/zwickroell/zwickroell-proline.json) | 계열 | universal_testing_machine | tensile, compression, flexure, peel, tear | 5–100 | – | crosshead_speed_mm_min=≤1000; vertical_test_space_mm=570–1450; horizontal_test_space_mm=440–640 | limited |
| [zwickroell-shore-hardness-testers](equipment/zwickroell/zwickroell-shore-hardness-testers.json) | 계열 | shore_irhd_hardness | hardness_shore | – | – | hardness_scales=Shore A, Shore D, Shore B, Shore C, Shore D0, Shore 0, Shore 00, Shore 000; specimen_thickness_mm=≥6; specimen_diameter_mm=≥35 | catalog |
| [zwickroell-temperature-chambers-allroundline](equipment/zwickroell/zwickroell-temperature-chambers-allroundline.json) | **부속** | environmental_chamber | tensile, compression, flexure | – | -80–250 | heating_rate_K_min=7.5–13 | catalog |
| [zwickroell-vibrophore](equipment/zwickroell/zwickroell-vibrophore.json) | 계열 | resonance_fatigue | fatigue, fracture_toughness, tensile, compression, flexure, torsion | – | – | dynamic_force_kN=15–1000; frequency_Hz=30–285; crosshead_speed_mm_min=0.0001–600; vertical_test_space_mm=≤2310; horizontal_test_space_mm=626, 982 | catalog |
| [zwickroell-zhr-rockwell](equipment/zwickroell/zwickroell-zhr-rockwell.json) | 계열 | rockwell_hardness | hardness_rockwell, hardness_brinell, hardness_vickers | – | – | test_load_kgf=6.25–250; hardness_scales=HRA–HRV, HR15/30/45 N/T/W/X/Y, HRα plastics E/L/M/R, HR2.5 ball, HBT, HVT 10–100, ball indentation 49–961 N; specimen_he | catalog |
| [zwickroell-zhu250](equipment/zwickroell/zwickroell-zhu250.json) | 기종 | universal_hardness | hardness_vickers, hardness_knoop, hardness_brinell, hardness_rockwell | – | – | test_load_kgf=1–250; hardness_scales=HV1–HV100, HVT, HK1, HBW 1/1 – 10/250, HBT, HRA/B/C/D/E/F/G/H/K, HR15/30/45 N/T, ball indentation 49–961 N; specimen_height | catalog |
