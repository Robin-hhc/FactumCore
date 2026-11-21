/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02804(unsigned int count)
{
    const unsigned int limit = 117u;
    return count > limit ? limit : count;
}
