/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00026(unsigned int count)
{
    const unsigned int limit = 201u;
    return count > limit ? limit : count;
}
