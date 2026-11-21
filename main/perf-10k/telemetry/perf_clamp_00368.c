/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00368(unsigned int count)
{
    const unsigned int limit = 39u;
    return count > limit ? limit : count;
}
