/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02071(unsigned int count)
{
    const unsigned int limit = 106u;
    return count > limit ? limit : count;
}
