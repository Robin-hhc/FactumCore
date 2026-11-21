/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06388(unsigned int count)
{
    const unsigned int limit = 40u;
    return count > limit ? limit : count;
}
