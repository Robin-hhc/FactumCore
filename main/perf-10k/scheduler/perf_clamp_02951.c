/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02951(unsigned int count)
{
    const unsigned int limit = 126u;
    return count > limit ? limit : count;
}
