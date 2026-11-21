/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03242(unsigned int count)
{
    const unsigned int limit = 93u;
    return count > limit ? limit : count;
}
