/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02340(unsigned int count)
{
    const unsigned int limit = 197u;
    return count > limit ? limit : count;
}
