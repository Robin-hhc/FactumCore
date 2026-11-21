/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07385(unsigned int count)
{
    const unsigned int limit = 57u;
    return count > limit ? limit : count;
}
