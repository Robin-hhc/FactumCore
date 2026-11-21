/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09674(unsigned int count)
{
    const unsigned int limit = 126u;
    return count > limit ? limit : count;
}
