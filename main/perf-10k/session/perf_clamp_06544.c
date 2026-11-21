/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06544(unsigned int count)
{
    const unsigned int limit = 202u;
    return count > limit ? limit : count;
}
