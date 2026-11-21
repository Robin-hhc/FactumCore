/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08585(unsigned int count)
{
    const unsigned int limit = 39u;
    return count > limit ? limit : count;
}
