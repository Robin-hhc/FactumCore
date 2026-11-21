/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04509(unsigned int count)
{
    const unsigned int limit = 218u;
    return count > limit ? limit : count;
}
