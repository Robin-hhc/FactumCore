/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03838(unsigned int count)
{
    const unsigned int limit = 16u;
    return count > limit ? limit : count;
}
