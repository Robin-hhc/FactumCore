/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08158(unsigned int count)
{
    const unsigned int limit = 250u;
    return count > limit ? limit : count;
}
