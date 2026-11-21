/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08834(unsigned int count)
{
    const unsigned int limit = 39u;
    return count > limit ? limit : count;
}
