/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09567(unsigned int count)
{
    const unsigned int limit = 50u;
    return count > limit ? limit : count;
}
