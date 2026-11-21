/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03683(unsigned int count)
{
    const unsigned int limit = 120u;
    return count > limit ? limit : count;
}
