#!/usr/bin/env python3
"""
SORGAM 3-mode lognormal mass partitioning calculator.

Uses the same lognormal size distribution as WRF-Chem SORGAM
(module_data_sorgam.F / module_aerosols_sorgam.F) to partition
total aerosol mass into nuclei (Aitken), accumulation, and coarse modes.

Lognormal distribution for each mode:
    n(d) = N / (ln(sigma_g) * sqrt(2*pi))
           * exp( -(ln(d/dg))^2 / (2 * ln(sigma_g)^2) )

k-th moment:
    M_k = N * dg^k * exp( k^2/2 * ln(sigma_g)^2 )

Mass (proportional to 3rd moment / volume):
    M3 = N * dg^3 * exp(9/2 * ln(sigma_g)^2)
       = N * dg^3 * es36

where es36 = exp(9/2 * ln(sigma_g)^2) following the SORGAM convention
      es36 = [exp(ln(sigma_g)^2 / 8)]^36
"""

import numpy as np


# ---------------------------------------------------------------------------
# WRF-Chem SORGAM default parameters (from module_data_sorgam.F)
# ---------------------------------------------------------------------------

# Default geometric mean number diameters [m]
DGININ_DEFAULT = 0.01e-6   # Aitken (nuclei) mode
DGINIA_DEFAULT = 0.07e-6   # Accumulation mode
DGINIC_DEFAULT = 1.0e-6    # Coarse mode

# Default geometric standard deviations [-]
SGININ_DEFAULT = 1.70      # Aitken (nuclei) mode
SGINIA_DEFAULT = 2.00      # Accumulation mode
SGINIC_DEFAULT = 2.50      # Coarse mode

# Component densities [kg m^-3] from module_data_sorgam.F
RHO_SO4  = 1.8e3
RHO_NH4  = 1.8e3
RHO_NO3  = 1.8e3
RHO_H2O  = 1.0e3
RHO_ORG  = 1.0e3
RHO_SOIL = 2.6e3
RHO_SEAS = 2.2e3
RHO_ANTH = 2.2e3   # also used for EC, P25
RHO_NA   = 2.2e3
RHO_CL   = 2.2e3


def compute_es36(sigma_g):
    """
    Compute the SORGAM es36 factor: exp(9/2 * [ln(sigma_g)]^2).

    This converts between the 0th moment (number) and 3rd moment (volume)
    of a lognormal distribution:
        M3 = N * dg^3 * es36
    """
    return np.exp(4.5 * np.log(sigma_g) ** 2)


def compute_volume_moment(N, dg, sigma_g):
    """
    Compute 3rd moment (proportional to volume) for a single lognormal mode.

    Parameters
    ----------
    N : float or array
        Number concentration [# m^-3 or any consistent unit].
    dg : float
        Geometric mean number diameter [m].
    sigma_g : float
        Geometric standard deviation [-].

    Returns
    -------
    M3 : float or array
        3rd moment concentration [m^3 m^-3].
    """
    es36 = compute_es36(sigma_g)
    return N * dg ** 3 * es36


def number_from_mass(mass_conc, dg, sigma_g, rho=RHO_ANTH):
    """
    Derive number concentration from mass concentration for a single mode,
    following the SORGAM initialization approach.

    mass_conc [ug m^-3]  -->  volume  -->  3rd moment  -->  number

    Parameters
    ----------
    mass_conc : float or array
        Mass concentration [ug m^-3].
    dg : float
        Geometric mean number diameter [m].
    sigma_g : float
        Geometric standard deviation [-].
    rho : float
        Bulk density [kg m^-3].

    Returns
    -------
    N : float or array
        Number concentration [# m^-3].
    """
    # Convert mass [ug m^-3] to 3rd moment [m^3 m^-3]
    # factor = (6 / pi) * 1e-9 / rho   (SORGAM: f6dpim9 / rho)
    fac = (6.0 / np.pi) * 1.0e-9 / rho
    m3 = fac * mass_conc

    es36 = compute_es36(sigma_g)
    return m3 / (dg ** 3 * es36)


def partition_mass(dg_nuc, dg_acc, dg_cor,
                   sigma_nuc, sigma_acc, sigma_cor,
                   f_nuc, f_acc, f_cor,
                   q_total, N_total):
    """
    Partition total aerosol mass into three lognormal modes using the same
    distribution as WRF-Chem SORGAM.

    The total particle population is described by three overlapping lognormal
    sub-distributions.  Given total number N_total split by number fractions
    (f_nuc, f_acc, f_cor), and each mode's geometric mean diameter and
    standard deviation, compute the mass (volume) in each mode.

    The 3rd moment (volume) of each mode is:
        M3_mode = N_mode * dg_mode^3 * es36_mode

    Mass is proportional to volume weighted by density.  For a single bulk
    density rho:
        mass_mode = rho * (pi/6) * M3_mode

    The fractional mass partitioning is independent of the common density:
        f_mass_mode = M3_mode / (M3_nuc + M3_acc + M3_cor)

    Parameters
    ----------
    dg_nuc, dg_acc, dg_cor : float
        Geometric mean number diameters for nuclei, accumulation, and
        coarse modes [m].
    sigma_nuc, sigma_acc, sigma_cor : float
        Geometric standard deviations for each mode [-].
    f_nuc, f_acc, f_cor : float
        Number fractions for each mode (should sum to 1).
    q_total : float
        Total aerosol mass concentration [ug m^-3].
    N_total : float
        Total number concentration [# m^-3] (= total CCN if all activated).

    Returns
    -------
    result : dict with keys:
        'N_nuc', 'N_acc', 'N_cor'   : mode number concentrations [# m^-3]
        'M3_nuc', 'M3_acc', 'M3_cor': mode 3rd moments [m^3 m^-3]
        'mass_nuc', 'mass_acc', 'mass_cor' : mode mass [ug m^-3]
        'frac_nuc', 'frac_acc', 'frac_cor' : mass fractions [-]
        'es36_nuc', 'es36_acc', 'es36_cor' : moment conversion factors
    """
    # Normalize fractions
    f_sum = f_nuc + f_acc + f_cor
    f_nuc, f_acc, f_cor = f_nuc / f_sum, f_acc / f_sum, f_cor / f_sum

    # Number concentrations per mode
    N_nuc = f_nuc * N_total
    N_acc = f_acc * N_total
    N_cor = f_cor * N_total

    # es36 factors (SORGAM convention)
    es36_nuc = compute_es36(sigma_nuc)
    es36_acc = compute_es36(sigma_acc)
    es36_cor = compute_es36(sigma_cor)

    # 3rd moment (volume) per mode  [m^3 m^-3]
    M3_nuc = N_nuc * dg_nuc ** 3 * es36_nuc
    M3_acc = N_acc * dg_acc ** 3 * es36_acc
    M3_cor = N_cor * dg_cor ** 3 * es36_cor

    M3_total = M3_nuc + M3_acc + M3_cor

    # Mass fractions (density-independent)
    frac_nuc = M3_nuc / M3_total
    frac_acc = M3_acc / M3_total
    frac_cor = M3_cor / M3_total

    # Absolute mass in each mode [ug m^-3]
    mass_nuc = frac_nuc * q_total
    mass_acc = frac_acc * q_total
    mass_cor = frac_cor * q_total

    return {
        # Number concentrations
        'N_nuc': N_nuc,
        'N_acc': N_acc,
        'N_cor': N_cor,
        # 3rd moments
        'M3_nuc': M3_nuc,
        'M3_acc': M3_acc,
        'M3_cor': M3_cor,
        'M3_total': M3_total,
        # Mass
        'mass_nuc': mass_nuc,
        'mass_acc': mass_acc,
        'mass_cor': mass_cor,
        # Mass fractions
        'frac_nuc': frac_nuc,
        'frac_acc': frac_acc,
        'frac_cor': frac_cor,
        # es36 factors
        'es36_nuc': es36_nuc,
        'es36_acc': es36_acc,
        'es36_cor': es36_cor,
    }


def partition_mass_multicomponent(dg_nuc, dg_acc, dg_cor,
                                  sigma_nuc, sigma_acc, sigma_cor,
                                  f_nuc, f_acc, f_cor,
                                  N_total, species_mass_dict):
    """
    Multi-component mass partitioning exactly matching SORGAM's 3rd-moment
    summation (module_aerosols_sorgam.F lines 7562-7593).

    Each chemical species has its own density.  The 3rd moment for each mode
    is the sum of species-specific volume contributions:
        M3_mode = sum_s( mass_s_mode * f6dpim9 / rho_s )

    Because we partition species mass into modes by *volume fraction*, this
    function:
      1. Computes the volume-weighted 3rd moment for each mode from N and dg.
      2. Uses those volume fractions to split each species' total mass.
      3. Verifies consistency with SORGAM's mass-to-3rd-moment factors.

    Parameters
    ----------
    dg_nuc, dg_acc, dg_cor : float
        Geometric mean number diameters [m].
    sigma_nuc, sigma_acc, sigma_cor : float
        Geometric standard deviations [-].
    f_nuc, f_acc, f_cor : float
        Number fractions for each mode.
    N_total : float
        Total number concentration [# m^-3].
    species_mass_dict : dict
        Keys are species names, values are dicts with:
            'mass'    : total mass [ug m^-3]
            'density' : bulk density [kg m^-3]
        Example: {'SO4': {'mass': 5.0, 'density': 1800.0},
                  'ORG': {'mass': 3.0, 'density': 1000.0}}

    Returns
    -------
    result : dict
        For each species, the mass in each mode plus total mass fractions.
    """
    f_sum = f_nuc + f_acc + f_cor
    f_nuc, f_acc, f_cor = f_nuc / f_sum, f_acc / f_sum, f_cor / f_sum

    N_nuc = f_nuc * N_total
    N_acc = f_acc * N_total
    N_cor = f_cor * N_total

    es36_nuc = compute_es36(sigma_nuc)
    es36_acc = compute_es36(sigma_acc)
    es36_cor = compute_es36(sigma_cor)

    M3_nuc = N_nuc * dg_nuc ** 3 * es36_nuc
    M3_acc = N_acc * dg_acc ** 3 * es36_acc
    M3_cor = N_cor * dg_cor ** 3 * es36_cor
    M3_total = M3_nuc + M3_acc + M3_cor

    vol_frac_nuc = M3_nuc / M3_total
    vol_frac_acc = M3_acc / M3_total
    vol_frac_cor = M3_cor / M3_total

    f6dpim9 = (6.0 / np.pi) * 1.0e-9

    result = {
        'volume_fractions': {
            'nuc': vol_frac_nuc,
            'acc': vol_frac_acc,
            'cor': vol_frac_cor,
        },
        'number': {'N_nuc': N_nuc, 'N_acc': N_acc, 'N_cor': N_cor},
        'M3': {'nuc': M3_nuc, 'acc': M3_acc, 'cor': M3_cor},
        'species': {},
    }

    total_mass_all = 0.0
    total_mass_nuc = 0.0
    total_mass_acc = 0.0
    total_mass_cor = 0.0

    for name, spec in species_mass_dict.items():
        mass = spec['mass']
        rho = spec['density']
        fac = f6dpim9 / rho   # SORGAM mass-to-M3 factor

        # Total 3rd moment from this species
        m3_species = fac * mass

        # Partition mass by volume fraction
        m_nuc = vol_frac_nuc * mass
        m_acc = vol_frac_acc * mass
        m_cor = vol_frac_cor * mass

        result['species'][name] = {
            'total_mass': mass,
            'mass_nuc': m_nuc,
            'mass_acc': m_acc,
            'mass_cor': m_cor,
            'mass_to_m3_factor': fac,
            'm3_contribution': m3_species,
        }

        total_mass_all += mass
        total_mass_nuc += m_nuc
        total_mass_acc += m_acc
        total_mass_cor += m_cor

    result['total'] = {
        'mass': total_mass_all,
        'mass_nuc': total_mass_nuc,
        'mass_acc': total_mass_acc,
        'mass_cor': total_mass_cor,
        'frac_nuc': total_mass_nuc / total_mass_all if total_mass_all > 0 else 0,
        'frac_acc': total_mass_acc / total_mass_all if total_mass_all > 0 else 0,
        'frac_cor': total_mass_cor / total_mass_all if total_mass_all > 0 else 0,
    }

    return result


def print_results(res, label="Mass Partitioning Results"):
    """Pretty-print partition_mass() output."""
    print("=" * 70)
    print(f"  {label}")
    print("=" * 70)

    print("\n--- Mode Parameters ---")
    print(f"  {'Mode':<15} {'es36':>12}  {'N [# m-3]':>14}  {'M3 [m3 m-3]':>14}")
    print(f"  {'Nuclei':<15} {res['es36_nuc']:12.4f}  {res['N_nuc']:14.4e}  {res['M3_nuc']:14.4e}")
    print(f"  {'Accumulation':<15} {res['es36_acc']:12.4f}  {res['N_acc']:14.4e}  {res['M3_acc']:14.4e}")
    print(f"  {'Coarse':<15} {res['es36_cor']:12.4f}  {res['N_cor']:14.4e}  {res['M3_cor']:14.4e}")

    print("\n--- Mass Partitioning ---")
    print(f"  {'Mode':<15} {'Mass [ug m-3]':>14}  {'Mass Fraction':>14}")
    print(f"  {'Nuclei':<15} {res['mass_nuc']:14.4e}  {res['frac_nuc']:14.6f}")
    print(f"  {'Accumulation':<15} {res['mass_acc']:14.4e}  {res['frac_acc']:14.6f}")
    print(f"  {'Coarse':<15} {res['mass_cor']:14.4e}  {res['frac_cor']:14.6f}")
    print(f"  {'Total':<15} {res['mass_nuc']+res['mass_acc']+res['mass_cor']:14.4e}  {1.0:14.6f}")
    print()


def print_multicomponent_results(res, label="Multi-Component Results"):
    """Pretty-print partition_mass_multicomponent() output."""
    print("=" * 70)
    print(f"  {label}")
    print("=" * 70)

    vf = res['volume_fractions']
    print(f"\n  Volume fractions:  nuc={vf['nuc']:.6f}  "
          f"acc={vf['acc']:.6f}  cor={vf['cor']:.6f}")

    nn = res['number']
    print(f"  Number [# m-3]:   nuc={nn['N_nuc']:.4e}  "
          f"acc={nn['N_acc']:.4e}  cor={nn['N_cor']:.4e}")

    print(f"\n  {'Species':<10} {'Total':>10} {'Nuc':>10} {'Acc':>10} "
          f"{'Cor':>10}  {'M3 factor':>12}  [ug m-3]")
    print("  " + "-" * 66)
    for name, sp in res['species'].items():
        print(f"  {name:<10} {sp['total_mass']:10.3f} {sp['mass_nuc']:10.3f} "
              f"{sp['mass_acc']:10.3f} {sp['mass_cor']:10.3f}  "
              f"{sp['mass_to_m3_factor']:12.4e}")

    t = res['total']
    print("  " + "-" * 66)
    print(f"  {'TOTAL':<10} {t['mass']:10.3f} {t['mass_nuc']:10.3f} "
          f"{t['mass_acc']:10.3f} {t['mass_cor']:10.3f}")
    print(f"  {'FRACTION':<10} {'':>10} {t['frac_nuc']:10.6f} "
          f"{t['frac_acc']:10.6f} {t['frac_cor']:10.6f}")
    print()


def partition_from_activation(dg_nuc, dg_acc, dg_cor,
                              sigma_nuc, sigma_acc, sigma_cor,
                              f_num_nuc, f_num_acc, f_num_cor,
                              f_act_nuc, f_act_acc, f_act_cor,
                              CCN_total, q_total,
                              rho_air=1.225, rho_aer=RHO_ANTH):
    """
    Estimate mass partitioning from observed activation fractions and CCN.

    In WRF-Chem SORGAM, each mode has an activation fraction (fn variables
    in registry.chem):
        CCN_total = f_act_nuc * N_nuc + f_act_acc * N_acc + f_act_cor * N_cor

    Given assumed number fractions (f_num) and observed CCN_total, we
    back out the total number and each mode's number, then partition mass.

    The physical logic:
    -----------------------------------------------------------------------
    Step 1: N_total = CCN_total / sum(f_act_i * f_num_i)

        Because:  CCN = sum( f_act_i * f_num_i * N_total )
        This gives the TOTAL particle number consistent with the
        observed CCN and activation fractions.

    Step 2: N_i = f_num_i * N_total  (number per mode)

    Step 3: M3_i = N_i * dg_i^3 * es36_i   (volume per mode)

    Step 4: mass_frac_i = M3_i / sum(M3_i)

    Parameters
    ----------
    dg_nuc, dg_acc, dg_cor : float
        Geometric mean number diameters [m].
    sigma_nuc, sigma_acc, sigma_cor : float
        Geometric standard deviations [-].
    f_num_nuc, f_num_acc, f_num_cor : float
        Assumed number fractions per mode (must sum to ~1).
    f_act_nuc, f_act_acc, f_act_cor : float
        Aerosol activation fractions per mode (0-1).
        From WRF output: fn11, fn21, fn31 (or similar).
    CCN_total : float
        Total CCN number concentration [# cm^-3].
    q_total : float
        Total aerosol mass mixing ratio [kg kg^-1].
    rho_air : float
        Air density [kg m^-3] for unit conversion. Default 1.225.
    rho_aer : float
        Bulk aerosol density [kg m^-3] for mass consistency check.

    Returns
    -------
    result : dict
        Complete partitioning results including derived N_total, mode
        numbers, mass fractions, and mass mixing ratios per mode.
    """
    # --- Step 1: Derive total N from CCN and activation fractions ---
    f_sum = f_num_nuc + f_num_acc + f_num_cor
    f_num_nuc /= f_sum
    f_num_acc /= f_sum
    f_num_cor /= f_sum

    # Effective activated fraction of total population
    f_act_eff = (f_act_nuc * f_num_nuc +
                 f_act_acc * f_num_acc +
                 f_act_cor * f_num_cor)

    # CCN [# cm^-3] -> [# m^-3]
    CCN_m3 = CCN_total * 1.0e6

    N_total = CCN_m3 / f_act_eff  # total particle number [# m^-3]

    # --- Step 2: Number per mode ---
    N_nuc = f_num_nuc * N_total
    N_acc = f_num_acc * N_total
    N_cor = f_num_cor * N_total

    # --- Step 3: 3rd moment (volume) per mode ---
    es36_nuc = compute_es36(sigma_nuc)
    es36_acc = compute_es36(sigma_acc)
    es36_cor = compute_es36(sigma_cor)

    M3_nuc = N_nuc * dg_nuc ** 3 * es36_nuc
    M3_acc = N_acc * dg_acc ** 3 * es36_acc
    M3_cor = N_cor * dg_cor ** 3 * es36_cor
    M3_total = M3_nuc + M3_acc + M3_cor

    # --- Step 4: Mass fractions ---
    frac_nuc = M3_nuc / M3_total
    frac_acc = M3_acc / M3_total
    frac_cor = M3_cor / M3_total

    # --- Convert q_total [kg/kg] to [ug m^-3] for absolute masses ---
    # q [kg/kg] * rho_air [kg/m^3] = concentration [kg/m^3]
    # * 1e9 = [ug/m^3]
    q_total_ug = q_total * rho_air * 1.0e9  # [ug m^-3]

    mass_nuc = frac_nuc * q_total_ug
    mass_acc = frac_acc * q_total_ug
    mass_cor = frac_cor * q_total_ug

    # Mass mixing ratios per mode [kg/kg]
    q_nuc = frac_nuc * q_total
    q_acc = frac_acc * q_total
    q_cor = frac_cor * q_total

    return {
        # Derived totals
        'N_total': N_total,
        'N_total_cm3': N_total * 1e-6,
        'f_act_effective': f_act_eff,
        # Number per mode
        'N_nuc': N_nuc, 'N_acc': N_acc, 'N_cor': N_cor,
        'N_nuc_cm3': N_nuc * 1e-6, 'N_acc_cm3': N_acc * 1e-6,
        'N_cor_cm3': N_cor * 1e-6,
        # CCN per mode
        'CCN_nuc': f_act_nuc * N_nuc * 1e-6,
        'CCN_acc': f_act_acc * N_acc * 1e-6,
        'CCN_cor': f_act_cor * N_cor * 1e-6,
        # es36
        'es36_nuc': es36_nuc, 'es36_acc': es36_acc, 'es36_cor': es36_cor,
        # 3rd moments
        'M3_nuc': M3_nuc, 'M3_acc': M3_acc, 'M3_cor': M3_cor,
        'M3_total': M3_total,
        # Mass fractions
        'frac_nuc': frac_nuc, 'frac_acc': frac_acc, 'frac_cor': frac_cor,
        # Absolute mass [ug/m^3]
        'mass_nuc_ug': mass_nuc, 'mass_acc_ug': mass_acc,
        'mass_cor_ug': mass_cor, 'q_total_ug': q_total_ug,
        # Mass mixing ratio per mode [kg/kg]
        'q_nuc': q_nuc, 'q_acc': q_acc, 'q_cor': q_cor,
        'q_total': q_total,
    }


def print_activation_results(res, label="Activation-based Partitioning"):
    """Pretty-print partition_from_activation() output."""
    print("=" * 70)
    print(f"  {label}")
    print("=" * 70)

    print("\n  --- Step 1: Derive total N from CCN + activation fractions ---")
    print(f"    Effective activation fraction = {res['f_act_effective']:.4f}")
    print(f"    N_total = CCN / f_act_eff     = {res['N_total_cm3']:.2f} cm-3")

    print("\n  --- Step 2: Number concentration per mode ---")
    print(f"    {'Mode':<15} {'N [cm-3]':>12} {'CCN [cm-3]':>12}")
    print(f"    {'Nuclei':<15} {res['N_nuc_cm3']:12.2f} {res['CCN_nuc']:12.2f}")
    print(f"    {'Accumulation':<15} {res['N_acc_cm3']:12.2f} {res['CCN_acc']:12.2f}")
    print(f"    {'Coarse':<15} {res['N_cor_cm3']:12.2f} {res['CCN_cor']:12.2f}")
    print(f"    {'TOTAL':<15} {res['N_total_cm3']:12.2f} "
          f"{res['CCN_nuc']+res['CCN_acc']+res['CCN_cor']:12.2f}")

    print("\n  --- Step 3: 3rd moment (volume) per mode ---")
    print(f"    {'Mode':<15} {'es36':>10} {'M3 [m3/m3]':>14}")
    print(f"    {'Nuclei':<15} {res['es36_nuc']:10.4f} {res['M3_nuc']:14.4e}")
    print(f"    {'Accumulation':<15} {res['es36_acc']:10.4f} {res['M3_acc']:14.4e}")
    print(f"    {'Coarse':<15} {res['es36_cor']:10.4f} {res['M3_cor']:14.4e}")

    print("\n  --- Step 4: Mass partitioning ---")
    print(f"    {'Mode':<15} {'Mass frac':>10} {'q [kg/kg]':>14} {'Mass [ug/m3]':>14}")
    print(f"    {'Nuclei':<15} {res['frac_nuc']:10.6f} {res['q_nuc']:14.4e} "
          f"{res['mass_nuc_ug']:14.4e}")
    print(f"    {'Accumulation':<15} {res['frac_acc']:10.6f} {res['q_acc']:14.4e} "
          f"{res['mass_acc_ug']:14.4e}")
    print(f"    {'Coarse':<15} {res['frac_cor']:10.6f} {res['q_cor']:14.4e} "
          f"{res['mass_cor_ug']:14.4e}")
    print(f"    {'TOTAL':<15} {1.0:10.6f} {res['q_total']:14.4e} "
          f"{res['q_total_ug']:14.4e}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":

    # ===================================================================
    # YOUR OBSERVATION-BASED CASE
    # ===================================================================
    #
    # Known from observation / WRF output:
    #   - Total aerosol mass mixing ratio:  4.5e-10  kg/kg
    #   - Total CCN number concentration:   50       cm^-3
    #   - Activation fraction (nuclei):     0.7      (WRF fn11)
    #   - Activation fraction (accum):      0.8      (WRF fn21)
    #   - Activation fraction (coarse):     1.0      (WRF fn31)
    #
    # Use SORGAM default diameters and sigma values.
    # Assume typical number fractions (adjustable).
    # ===================================================================

    # --- SORGAM default distribution parameters ---
    dg_nuc  = DGININ_DEFAULT   # 0.01  um  (nuclei/Aitken mode)
    dg_acc  = DGINIA_DEFAULT   # 0.07  um  (accumulation mode)
    dg_cor  = DGINIC_DEFAULT   # 1.0   um  (coarse mode)

    sigma_nuc = SGININ_DEFAULT # 1.70
    sigma_acc = SGINIA_DEFAULT # 2.00
    sigma_cor = SGINIC_DEFAULT # 2.50

    # --- Your observations ---
    q_total    = 4.5e-10       # total aerosol mass mixing ratio [kg/kg]
    CCN_total  = 50.0          # total CCN [# cm^-3]
    f_act_nuc  = 0.7           # activation fraction, nuclei mode
    f_act_acc  = 0.8           # activation fraction, accumulation mode
    f_act_cor  = 1.0           # activation fraction, coarse mode

    # --- Assumed number fractions ---
    # These control how N_total is distributed among modes.
    # Typical remote/clean atmosphere: most particles by number in
    # nuclei mode, fewer in accumulation, very few in coarse.
    f_num_nuc = 0.80           # 80% of particles by NUMBER in nuclei
    f_num_acc = 0.19           # 19% in accumulation
    f_num_cor = 0.01           #  1% in coarse

    # --- Run the calculation ---
    res = partition_from_activation(
        dg_nuc, dg_acc, dg_cor,
        sigma_nuc, sigma_acc, sigma_cor,
        f_num_nuc, f_num_acc, f_num_cor,
        f_act_nuc, f_act_acc, f_act_cor,
        CCN_total, q_total,
    )
    print_activation_results(res,
        "Your case: q=4.5e-10 kg/kg, CCN=50 cm-3, f_act=0.7/0.8/1.0")

    # --- Sensitivity: vary assumed number fractions ---
    print("=" * 70)
    print("  Sensitivity to assumed number fractions")
    print("  (dg, sigma, q_total, CCN, f_act are all fixed)")
    print("=" * 70)
    print(f"\n  {'f_nuc':>6} {'f_acc':>6} {'f_cor':>6} | "
          f"{'N_tot':>8} | {'frac_nuc':>10} {'frac_acc':>10} {'frac_cor':>10} | "
          f"{'q_nuc':>12} {'q_acc':>12} {'q_cor':>12}")
    print(f"  {'':>6} {'':>6} {'':>6} | "
          f"{'[cm-3]':>8} | {'':>10} {'':>10} {'':>10} | "
          f"{'[kg/kg]':>12} {'[kg/kg]':>12} {'[kg/kg]':>12}")
    print("  " + "-" * 110)

    test_fracs = [
        (0.90, 0.09, 0.01),   # dominated by nuclei
        (0.80, 0.19, 0.01),   # typical (default)
        (0.70, 0.28, 0.02),   # more accumulation
        (0.50, 0.45, 0.05),   # bimodal
        (0.30, 0.60, 0.10),   # accumulation dominated
    ]

    for fn, fa, fc in test_fracs:
        r = partition_from_activation(
            dg_nuc, dg_acc, dg_cor,
            sigma_nuc, sigma_acc, sigma_cor,
            fn, fa, fc,
            f_act_nuc, f_act_acc, f_act_cor,
            CCN_total, q_total,
        )
        print(f"  {fn:6.2f} {fa:6.2f} {fc:6.2f} | "
              f"{r['N_total_cm3']:8.2f} | "
              f"{r['frac_nuc']:10.6f} {r['frac_acc']:10.6f} "
              f"{r['frac_cor']:10.6f} | "
              f"{r['q_nuc']:12.4e} {r['q_acc']:12.4e} {r['q_cor']:12.4e}")
    print()

    # --- Verification ---
    print("=" * 70)
    print("  Verification: SORGAM es36 factors")
    print("=" * 70)
    print(f"  esn36 (sigma={sigma_nuc}): {compute_es36(sigma_nuc):.6f}")
    print(f"  esa36 (sigma={sigma_acc}): {compute_es36(sigma_acc):.6f}")
    print(f"  esc36 (sigma={sigma_cor}): {compute_es36(sigma_cor):.6f}")
    print()
