/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08937(unsigned int count)
{
    const unsigned int limit = 47u;
    return count > limit ? limit : count;
}
