/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09272(unsigned int count)
{
    const unsigned int limit = 15u;
    return count > limit ? limit : count;
}
