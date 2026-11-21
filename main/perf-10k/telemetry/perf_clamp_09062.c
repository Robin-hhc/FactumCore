/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09062(unsigned int count)
{
    const unsigned int limit = 180u;
    return count > limit ? limit : count;
}
