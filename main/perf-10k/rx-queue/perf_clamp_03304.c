/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03304(unsigned int count)
{
    const unsigned int limit = 151u;
    return count > limit ? limit : count;
}
