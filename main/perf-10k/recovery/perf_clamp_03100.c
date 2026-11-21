/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03100(unsigned int count)
{
    const unsigned int limit = 169u;
    return count > limit ? limit : count;
}
