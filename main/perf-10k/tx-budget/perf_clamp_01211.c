/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01211(unsigned int count)
{
    const unsigned int limit = 177u;
    return count > limit ? limit : count;
}
