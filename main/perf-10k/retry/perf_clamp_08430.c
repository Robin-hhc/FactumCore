/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08430(unsigned int count)
{
    const unsigned int limit = 143u;
    return count > limit ? limit : count;
}
