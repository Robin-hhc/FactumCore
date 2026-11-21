/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02713(unsigned int count)
{
    const unsigned int limit = 64u;
    return count > limit ? limit : count;
}
