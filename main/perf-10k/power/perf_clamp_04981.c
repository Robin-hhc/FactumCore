/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04981(unsigned int count)
{
    const unsigned int limit = 25u;
    return count > limit ? limit : count;
}
