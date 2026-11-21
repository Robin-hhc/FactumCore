/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04535(unsigned int count)
{
    const unsigned int limit = 162u;
    return count > limit ? limit : count;
}
