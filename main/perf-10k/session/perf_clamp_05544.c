/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05544(unsigned int count)
{
    const unsigned int limit = 134u;
    return count > limit ? limit : count;
}
