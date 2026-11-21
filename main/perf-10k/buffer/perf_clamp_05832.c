/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05832(unsigned int count)
{
    const unsigned int limit = 50u;
    return count > limit ? limit : count;
}
